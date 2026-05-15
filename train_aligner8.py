"""Custom training mission: aligner tutorial with 8 agents for competition transfer."""

from cogames.cogs_vs_clips.tutorials.aligner_tutorial import (
    COGSGUARD_ARENA, AlignerRewardsVariant, CogConfig, CogTeam, CvCMission, EASY,
)

NUM_AGENTS = 8
MAX_STEPS = 1000

mission = CvCMission(
    name="aligner_tutorial_8agents",
    description="Aligner tutorial with 8 agents for competition transfer.",
    site=COGSGUARD_ARENA,
    num_cogs=NUM_AGENTS,
    max_steps=MAX_STEPS,
    cog=CogConfig(heart_limit=3),
    teams={"cogs": CogTeam(name="cogs", num_agents=NUM_AGENTS, wealth=3, initial_hearts=120)},
    variants=[EASY, AlignerRewardsVariant()],
)

config = mission.make_env()
