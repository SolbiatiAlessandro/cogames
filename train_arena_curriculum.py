"""Training mission: arena basic with clips and small initial hearts for competition transfer.

Uses initial_hearts=15 (vs 60 in bootstrap, vs 0 in competition) as a middle ground.
This forces agents to learn mining+crafting while still having some hearts to bootstrap
alignment learning. wealth=1 matches competition exactly.
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam

arena_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_arena':
            arena_basic = m
            break

if arena_basic is None:
    raise ValueError("Could not find cogsguard_arena.basic mission")

arena_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

config = arena_basic.make_env()

apply_reward_variants(config, variants=["milestones_2", "credit"])
