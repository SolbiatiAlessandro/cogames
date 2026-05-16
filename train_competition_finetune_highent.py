"""Fine-tune the best competition model (5act epoch 20) with high entropy.

The 5act model had avg alignment 0.36 epochs 16-20 but showed 0 on eval.
High entropy (0.02) might recover exploration behavior and allow the
already-trained alignment skills to generalize to more maps.

Uses the same reward structure as the original (milestones_2 + credit)
but with exploration bonus to push agents beyond hub.
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

apply_reward_variants(config, variants=["milestones_2", "credit"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.01,
    )
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=2.0,
    )
    agent_cfg.rewards = rewards
