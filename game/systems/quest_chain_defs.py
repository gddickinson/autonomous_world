"""Built-in quest chain definitions.

Contains factory functions for each pre-designed multi-stage quest chain.
Each function creates a QuestChain with stages, conditions, and branch
choices already configured.

Quest chains:
- The Bandit Problem: 3 stages, combat/diplomacy branch
- The Missing Merchant: 3 stages, rescue/delivery branch
- Ancient Secrets: 4 stages, 3-way branch (scholar/self/temple)
"""

from game.systems.quest_chains import (
    QuestChain, QuestStage, StageCondition, BranchChoice,
    CONDITION_KILL, CONDITION_LOCATION, CONDITION_ITEM,
    CONDITION_TALK, CONDITION_DELIVER,
)


def create_bandit_problem(settlement: str = "the settlement",
                          giver: str = "Guard Captain") -> QuestChain:
    """The Bandit Problem: 3 stages, combat or diplomacy branch."""
    stages = [
        QuestStage(
            title="Clear the Bandit Patrols",
            description=(f"Bandits have been raiding near {settlement}. "
                         "Kill 3 bandits lurking on the roads."),
            condition=StageCondition(CONDITION_KILL, "bandit", 3,
                                    "Kill 3 bandits near the settlement"),
            reward_gold=15, reward_xp=20,
        ),
        QuestStage(
            title="Find the Bandit Camp",
            description=("Follow the trail from the slain bandits back "
                         "to their hidden camp in the wilderness."),
            condition=StageCondition(CONDITION_LOCATION, "bandit camp", 1,
                                    "Locate the bandit camp"),
            reward_gold=25, reward_xp=30,
        ),
        QuestStage(
            title="Deal with the Bandits",
            description="You've found the camp. How will you end this?",
            condition=StageCondition(CONDITION_KILL, "", 0),
            branch_choices=[
                BranchChoice(
                    label="Negotiate Peace",
                    description="Try to convince the bandit leader to disband.",
                    skill_check="diplomacy", dc=14,
                    reward_gold=50, reward_xp=60,
                    reward_reputation=15,
                    outcome_text=(
                        "The bandit leader agrees to lay down arms. "
                        "Some may even join the settlement militia."),
                ),
                BranchChoice(
                    label="Destroy the Camp",
                    description="Burn the camp and scatter the bandits by force.",
                    skill_check="combat", dc=12,
                    reward_gold=50, reward_xp=80,
                    reward_item="Blade of the Dawn",
                    outcome_text=(
                        "The camp is ablaze. Among the ashes you find "
                        "a radiant blade — the Blade of the Dawn."),
                ),
            ],
        ),
    ]
    return QuestChain(
        chain_id="bandit_problem",
        name="The Bandit Problem",
        stages=stages,
        settlement=settlement,
        giver_name=giver,
    )


def create_missing_merchant(settlement: str = "the settlement",
                            destination: str = "the crossroads",
                            giver: str = "Innkeeper") -> QuestChain:
    """The Missing Merchant: 3 stages, rescue or recovery branch."""
    stages = [
        QuestStage(
            title="Ask About the Merchant",
            description=(f"A merchant hasn't returned to {settlement}. "
                         "Talk to the innkeeper for information."),
            condition=StageCondition(CONDITION_TALK, giver, 1,
                                    "Talk to the innkeeper"),
            reward_gold=0, reward_xp=10,
        ),
        QuestStage(
            title="Search the Road",
            description=(f"Search the road between {settlement} and "
                         f"{destination} for clues about the merchant."),
            condition=StageCondition(CONDITION_LOCATION, destination, 1,
                                    "Search the road for clues"),
            reward_gold=15, reward_xp=25,
        ),
        QuestStage(
            title="The Merchant's Fate",
            description="You found signs of struggle. What happened here?",
            condition=StageCondition(CONDITION_KILL, "", 0),
            branch_choices=[
                BranchChoice(
                    label="Rescue from Bandits",
                    description="The merchant is alive, held captive. Fight!",
                    skill_check="combat", dc=13,
                    reward_gold=40, reward_xp=50,
                    reward_reputation=10,
                    outcome_text=(
                        "You free the merchant from captivity. "
                        "They are grateful and will remember your courage."),
                ),
                BranchChoice(
                    label="Recover the Goods",
                    description=(
                        "The merchant didn't make it, but the goods "
                        "can still be returned to the settlement."),
                    skill_check="", dc=0,
                    condition=StageCondition(CONDITION_DELIVER,
                                            "merchant goods", 1),
                    reward_gold=30, reward_xp=35,
                    reward_item="Greater Health Potion",
                    outcome_text=(
                        "You return the merchant's goods to "
                        f"{settlement}. A somber but necessary deed."),
                ),
            ],
        ),
    ]
    return QuestChain(
        chain_id="missing_merchant",
        name="The Missing Merchant",
        stages=stages,
        settlement=settlement,
        giver_name=giver,
    )


def create_ancient_secrets(settlement: str = "the settlement",
                           giver: str = "Scholar") -> QuestChain:
    """Ancient Secrets: 4 stages, 3-way branch at the end."""
    stages = [
        QuestStage(
            title="The Scholar's Request",
            description=(f"A scholar in {settlement} asks you to investigate "
                         "nearby ruins that may hold ancient knowledge."),
            condition=StageCondition(CONDITION_TALK, giver, 1,
                                    "Speak with the scholar about the ruins"),
            reward_gold=0, reward_xp=15,
        ),
        QuestStage(
            title="Explore the Dungeon",
            description=("Enter the ruins and fight your way to the inner "
                         "chamber where the artifact is said to be hidden."),
            condition=StageCondition(CONDITION_LOCATION, "ancient ruins", 1,
                                    "Find the artifact chamber"),
            reward_gold=20, reward_xp=40,
        ),
        QuestStage(
            title="Retrieve the Artifact",
            description="The artifact glows with power. Take it.",
            condition=StageCondition(CONDITION_ITEM, "ancient artifact", 1,
                                    "Pick up the ancient artifact"),
            reward_gold=25, reward_xp=35,
        ),
        QuestStage(
            title="The Artifact's Destiny",
            description=("You hold a relic of immense power. "
                         "Who will receive it?"),
            condition=StageCondition(CONDITION_ITEM, "", 0),
            branch_choices=[
                BranchChoice(
                    label="Give to Scholar",
                    description="Return the artifact for academic study.",
                    reward_gold=30, reward_xp=50,
                    reward_knowledge="Ancient Runecraft",
                    reward_reputation=20,
                    outcome_text=(
                        "The scholar's eyes light up. 'This will "
                        "advance our understanding by centuries!' "
                        "You gain deep knowledge of ancient runes."),
                ),
                BranchChoice(
                    label="Keep for Yourself",
                    description="The artifact's power is yours to wield.",
                    reward_gold=0, reward_xp=30,
                    reward_item="Cloak of Many Stars",
                    outcome_text=(
                        "The artifact transforms into a shimmering "
                        "cloak woven from starlight. The scholar is "
                        "disappointed, but you feel its power."),
                ),
                BranchChoice(
                    label="Give to Temple",
                    description="Donate the artifact to the local temple.",
                    reward_gold=50, reward_xp=40,
                    reward_reputation=35,
                    reward_item="Shield of the Faithful",
                    outcome_text=(
                        "The temple priests accept the artifact "
                        "with reverence and bestow upon you the "
                        "Shield of the Faithful as thanks."),
                ),
            ],
        ),
    ]
    return QuestChain(
        chain_id="ancient_secrets",
        name="Ancient Secrets",
        stages=stages,
        settlement=settlement,
        giver_name=giver,
    )


# Registry of all chain factory functions
CHAIN_FACTORIES = {
    "bandit_problem": create_bandit_problem,
    "missing_merchant": create_missing_merchant,
    "ancient_secrets": create_ancient_secrets,
}


def _register_main_quest():
    """Lazy-register the main questline to avoid circular imports."""
    if "the_awakening" not in CHAIN_FACTORIES:
        from game.systems.main_quest import create_the_awakening
        CHAIN_FACTORIES["the_awakening"] = create_the_awakening
