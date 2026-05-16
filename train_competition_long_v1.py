"""Competition map, FIXED seed 42, NO CLIPS, 5000 steps — V1 rewards (no wrong-gear penalties).

Matching V1 rewards exactly for checkpoint continuation from train_dir_long epoch 20.
V1 at epoch 20: 55% move success, max_steps=26.6, 0 alignment (gear loss problem).
Hypothesis: continuing to epoch 50+ with accumulated navigation skill may naturally
resolve gear retention as alignment reward (weight=20) dominates exploration.

Use with: COGAMES_ENT_START=0.005 COGAMES_ENT_END=0.005 COGAMES_ENT_ANNEAL_EPOCHS=1
(constant ent_coef=0.005 to match what model was trained at after epoch 10)
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
        weight=20.0,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=10.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=2.0,
    )
    agent_cfg.rewards = rewards
