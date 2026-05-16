"""Competition map: 5-action, 15 hearts, NAVIGATOR curriculum.

All previous training runs failed because agents never learned to navigate
beyond the hub. This config uses a radical approach: MASSIVE exploration reward
as the primary signal, with only tiny alignment rewards.

The idea: first teach the model to MOVE everywhere on the map. Once it can
navigate, the small alignment reward creates gradient toward junctions.

Rewards:
- cell.visited at 0.1 (100x the previous 0.001) — dominant reward signal
- milestones_2 at default — keeps alignment objective active
- No credit — no hub distractions
- Small alignment bonus — only kicks in when agent reaches junction

Use with COGAMES_ENT_COEF=0.02 for sustained exploration.
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant

from mettagrid.config.game_value import stat
from mettagrid.config.reward_config import reward

competition_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_machina_1':
            competition_basic = m
            break

if competition_basic is None:
    raise ValueError("Could not find cogsguard_machina_1.basic mission")

competition_basic.max_steps = 1000
competition_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

no_vibes = NoVibesVariant()
competition_basic.variants = list(getattr(competition_basic, 'variants', []))
competition_basic.variants.append(no_vibes)

config = competition_basic.make_env()

apply_reward_variants(config, variants=["milestones_2"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["exploration_dominant"] = reward(
        stat("cell.visited"),
        weight=0.1,
    )
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=2.0,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=0.5,
    )
    agent_cfg.rewards = rewards
