"""Arena 5-action with heavy exploration bonus + credit + entropy annealing.

Diagnosis: agents aren't finding aligner stations because exploration_bonus
is too weak (0.01). This variant increases it to 0.05 and adds a direct
aligner_gear reward of 5.0 to make gear acquisition a high-priority behavior.

Use with: COGAMES_ENT_START=0.08 COGAMES_ENT_END=0.01 COGAMES_ENT_ANNEAL_EPOCHS=30
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

apply_reward_variants(config, variants=["milestones_2:25", "credit"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=5.0,
    )
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.05,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=5.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=1.0,
    )
    agent_cfg.rewards = rewards
