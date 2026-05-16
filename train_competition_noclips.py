"""Competition map, FIXED seed 42, NO CLIPS — pure alignment learning.

Without clips ships, junctions stay aligned once cogs reach them. This lets the
model learn the full alignment pipeline (get gear → navigate → align) without
the adversarial scrambling that makes the reward signal noisy.

Once alignment is learned, fine-tune WITH clips to learn adversarial robustness.

Use with: COGAMES_ENT_START=0.10 COGAMES_ENT_END=0.02 COGAMES_ENT_ANNEAL_EPOCHS=30
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant, NoClipsVariant

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
no_clips = NoClipsVariant()
competition_basic.variants = list(getattr(competition_basic, 'variants', []))
competition_basic.variants.append(no_vibes)
competition_basic.variants.append(no_clips)

config = competition_basic.make_env()

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
        weight=10.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=2.0,
    )
    rewards["deposit_diversity"] = reward(
        [stat(f"{e}.lost") for e in _MINER_ELEMENTS],
        aggregation=Aggregation.SUM_LOGS,
        weight=0.15,
        max=2.0,
    )
    agent_cfg.rewards = rewards
