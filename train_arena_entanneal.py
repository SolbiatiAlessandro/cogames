"""Arena 5-action with credit + entropy annealing.

Key insight from experiments:
- Without credit: agents get ZERO alignment (no dense sub-goal rewards to guide learning)
- With credit + fixed ent: entropy collapses, alignment peaks then crashes
- Solution: credit (for discovery) + entropy annealing (start 0.08, end 0.01, 30 epochs)

Early training: high entropy forces exploration, credit rewards guide toward alignment
Late training: low entropy allows convergence to alignment-seeking behavior

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
        weight=0.01,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=2.0,
    )
    agent_cfg.rewards = rewards
