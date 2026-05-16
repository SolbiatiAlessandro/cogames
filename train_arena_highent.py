"""Arena 5-action: high entropy, no credit, strong per-tick objective.

Key changes vs previous experiments:
1. NO credit variant — credit's dense hub rewards accelerated entropy collapse
2. ent_coef=0.05 (via env var) — much higher than default 0.01 to prevent collapse
3. milestones_2:25 — 5x higher compounding factor makes per-tick alignment reward
   extremely dominant. Aligning one junction early = continuous reward for rest of ep.
4. Strong alignment bonus (10.0) + aligner gear bonus (3.0) + moderate exploration

The hypothesis: high entropy keeps exploration alive long enough for the model to
discover that alignment creates sustained reward through the per-tick objective.
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant

from mettagrid.config.game_value import stat
from mettagrid.config.reward_config import reward

arena_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_arena':
            arena_basic = m
            break

if arena_basic is None:
    raise ValueError("Could not find cogsguard_arena.basic mission")

arena_basic.max_steps = 1000
arena_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

no_vibes = NoVibesVariant()
arena_basic.variants = list(getattr(arena_basic, 'variants', []))
arena_basic.variants.append(no_vibes)

config = arena_basic.make_env()

apply_reward_variants(config, variants=["milestones_2:25"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=10.0,
    )
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.01,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=3.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=0.3,
    )
    agent_cfg.rewards = rewards
