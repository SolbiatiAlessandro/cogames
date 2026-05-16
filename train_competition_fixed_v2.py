"""Competition map, FIXED seed 42, stronger alignment signal.

Changes from train_competition_fixed.py:
- alignment_bonus weight=20.0 (4x higher — make alignment the dominant reward)
- aligner_gear_bonus weight=10.0 (2x — stronger gear pickup incentive)
- exploration_bonus weight=0.02 (reduced — don't drown out alignment)
- max_steps=4000 (longer episodes — more time to reach junctions)

Use with: COGAMES_ENT_START=0.10 COGAMES_ENT_END=0.02 COGAMES_ENT_ANNEAL_EPOCHS=40
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant

from mettagrid.config.game_value import stat
from mettagrid.config.reward_config import Aggregation, reward

_MINER_ELEMENTS = ("carbon", "oxygen", "germanium", "silicon")

competition_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_machina_1':
            competition_basic = m
            break

if competition_basic is None:
    raise ValueError("Could not find cogsguard_machina_1.basic mission")

competition_basic.max_steps = 4000
competition_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

no_vibes = NoVibesVariant()
competition_basic.variants = list(getattr(competition_basic, 'variants', []))
competition_basic.variants.append(no_vibes)

config = competition_basic.make_env()

config.game.map_builder.seed = 42

apply_reward_variants(config, variants=["milestones_2:25", "credit"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=20.0,
    )
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.02,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=10.0,
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
