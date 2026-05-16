"""Competition map, FIXED seed 42, NO CLIPS, 5000 steps — V4: high alignment reward.

Lessons learned from V1-V3:
- V1 (aligner.gained=10, alignment=20): good navigation (55% at e20) but 0 alignment.
  Exploration bonus (125) dominates alignment reward (20-40). Agent never learns
  "keep aligner → junction" because alignment signal is too weak.
- Long4 (wrong-gear penalties): navigation stalled at 16 (penalties slow exploration).
- V3 (aligner.lost=-10): gain+loss=net 0 removed incentive to approach stations.

V4 solution: same as V1 but TRIPLE the alignment reward (50.0 instead of 20.0).
After exploration saturates (~250 cells), alignment becomes the strongest marginal
reward. One junction alignment (50.0) = 40% of total exploration reward (125).

Also increase aligner.gained to 15.0 to make gear stations very attractive.
Keep NO penalties — let agents explore freely and learn from positive rewards.

Use with: COGAMES_ENT_START=0.05 COGAMES_ENT_END=0.005 COGAMES_ENT_ANNEAL_EPOCHS=10
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant, NoClipsVariant

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

competition_basic.max_steps = 5000
competition_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

no_vibes = NoVibesVariant()
no_clips = NoClipsVariant()
competition_basic.variants = list(getattr(competition_basic, 'variants', []))
competition_basic.variants.append(no_vibes)
competition_basic.variants.append(no_clips)

config = competition_basic.make_env()

config.game.map_builder.seed = 42

apply_reward_variants(config, variants=["milestones_2:25", "credit"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.5,
        max=250.0,
    )
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=50.0,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=15.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=3.0,
    )
    agent_cfg.rewards = rewards
