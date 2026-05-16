"""Competition map: 5-action, 15 hearts, ALIGNER variant + high entropy.

Every training run so far collapses alignment after epoch 13-20, correlating
with entropy dropping below ~1.2. This config:
1. Uses "aligner" reward variant (strong junction/gear rewards, penalizes wrong gear)
2. Runs with COGAMES_ENT_COEF=0.03 (3x default) to maintain exploration
3. Uses cell.visited exploration reward
4. Does NOT use credit variant (no dense hub rewards)

The hypothesis: higher entropy prevents the policy from over-committing to
hub-only behavior, maintaining enough stochasticity to keep discovering junctions.
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

apply_reward_variants(config, variants=["milestones_2", "aligner"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.01,
    )
    agent_cfg.rewards = rewards
