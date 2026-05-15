"""Training mission: arena basic with clips, initial hearts, and milestones_2.

Bridges the gap between easy tutorial (120 initial hearts, no clips) and
competition (no initial hearts, clips). Gives agents 60 initial hearts to
bootstrap alignment learning while still facing clips opposition.
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
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=2, initial_hearts=60),
}

config = arena_basic.make_env()

apply_reward_variants(config, variants=["milestones_2", "credit"])
