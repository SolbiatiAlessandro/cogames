"""Competition map: high entropy, no credit, strong per-tick objective.

Same reward philosophy as train_arena_highent.py but on the competition map
(cogsguard_machina_1.basic, 88×88). This is the actual tournament map.

With ent_coef=0.05 and no credit, entropy should remain high enough to prevent
collapse while the milestones_2:25 per-tick objective rewards sustained alignment.
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

apply_reward_variants(config, variants=["milestones_2:25"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=10.0,
    )
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.01,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=3.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=0.3,
    )
    agent_cfg.rewards = rewards
