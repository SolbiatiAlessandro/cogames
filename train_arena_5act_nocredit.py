"""Arena 5-action: NO credit variant, high entropy to prevent collapse.

Key insight: the credit variant provides dense hub rewards that accelerate
entropy collapse, even with ent_coef=0.02. This config removes credit entirely,
keeping only milestones_2 + strong alignment bonus.

On the 50x50 arena, junctions are ~7-10 tiles from hub center, within the
13x13 observation window. Without credit's dense rewards pulling agents to hub,
exploration + alignment should create gradient toward visible junctions.

Run with COGAMES_ENT_COEF=0.03 for maximum entropy stability.
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

apply_reward_variants(config, variants=["milestones_2"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=5.0,
    )
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.01,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=1.0,
    )
    agent_cfg.rewards = rewards
