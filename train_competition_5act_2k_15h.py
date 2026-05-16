"""Competition map: 5-action, 15 hearts, 2000 steps.

Combines the best findings:
- 5-action space (NoVibesVariant): 2x better alignment, no collapse
- 15 initial hearts: smooth transition to self-sustaining mining
- 2000 steps: closer to competition (10000) for longer-horizon behavior
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

competition_basic.max_steps = 2000

competition_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

no_vibes = NoVibesVariant()
competition_basic.variants = list(getattr(competition_basic, 'variants', []))
competition_basic.variants.append(no_vibes)

config = competition_basic.make_env()

apply_reward_variants(config, variants=["milestones_2", "credit"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["deposit_diversity"] = reward(
        [stat(f"{e}.lost") for e in _MINER_ELEMENTS],
        aggregation=Aggregation.SUM_LOGS,
        weight=0.15,
        max=2.0,
    )
    rewards["mining_diversity"] = reward(
        [stat(f"{e}.gained") for e in _MINER_ELEMENTS],
        aggregation=Aggregation.SUM_LOGS,
        weight=0.1,
        max=1.5,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=0.5,
    )
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=1.0,
    )
    agent_cfg.rewards = rewards
