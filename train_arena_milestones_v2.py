"""Training mission: arena basic with milestones_2 + credit reward shaping.

Same as train_arena_milestones.py but WITHOUT the aligner-specific variant.
The aligner variant penalizes non-aligner gear (-1.0), which may hurt early learning
when agents need to explore all gear types. milestones_2 alone already rewards
junction alignment and heart collection.
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants

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

apply_reward_variants(config, variants=["milestones_2", "credit"])
