"""Arena map, FIXED seed 42, 5-action, strong alignment signal.

Arena is 50x50 (vs 88x88 competition) - faster iterations, easier navigation.
Fixed seed forces model to learn specific paths on the eval map.
Credit + milestones_2:25 + aggressive alignment reward.

Use with: COGAMES_ENT_START=0.10 COGAMES_ENT_END=0.02 COGAMES_ENT_ANNEAL_EPOCHS=30
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant

from mettagrid.config.game_value import stat
from mettagrid.config.reward_config import Aggregation, reward

_MINER_ELEMENTS = ("carbon", "oxygen", "germanium", "silicon")

arena_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_arena':
            arena_basic = m
            break

if arena_basic is None:
    raise ValueError("Could not find cogsguard_arena.basic mission")

arena_basic.max_steps = 2000
arena_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

no_vibes = NoVibesVariant()
arena_basic.variants = list(getattr(arena_basic, 'variants', []))
arena_basic.variants.append(no_vibes)

config = arena_basic.make_env()

config.game.map_builder.seed = 42

apply_reward_variants(config, variants=["milestones_2:25", "credit"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=10.0,
    )
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.03,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=5.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=1.0,
    )
    rewards["deposit_diversity"] = reward(
        [stat(f"{e}.lost") for e in _MINER_ELEMENTS],
        aggregation=Aggregation.SUM_LOGS,
        weight=0.15,
        max=2.0,
    )
    agent_cfg.rewards = rewards
