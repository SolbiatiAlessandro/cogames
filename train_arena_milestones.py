"""Training mission: arena basic with milestones_2 reward shaping.

Combines the arena basic map (50x50, 8 agents, clips enabled) with milestones_2
reward shaping for dense learning signal. This is the best compromise between
learning speed and competition transfer.
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants

# Find cogsguard_arena.basic (the second mission in the list — 50x50, 8 agents)
arena_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_arena':
            arena_basic = m
            break

if arena_basic is None:
    raise ValueError("Could not find cogsguard_arena.basic mission")

config = arena_basic.make_env()

# Apply milestones_2 reward shaping — capped role-shaped rewards that
# favor alignment to unlock objective reward
apply_reward_variants(config, variants=["milestones_2", "credit", "aligner"])
