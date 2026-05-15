"""Training mission: arena with balanced deposit + alignment rewards.

Fixes the deposit-only config where uncapped mining rewards dominated
alignment incentives. Key changes:
- Reduced deposit_diversity weight: 0.3 → 0.15 (with cap=2.0)
- Reduced mining_diversity weight: 0.2 → 0.1 (with cap=1.5)
- Added explicit aligner gear reward: weight=0.5 (uncapped)
- Added junction alignment bonus: weight=1.0 (stacks with milestones_2)

initial_hearts=15, wealth=1 to match competition.
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam

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

arena_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

config = arena_basic.make_env()

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
