"""Competition map, FIXED seed 42, NO CLIPS, 5000 steps — long episodes for junction reach.

The math: random walk range = sqrt(steps × move_success_rate).
- 2000 steps, 34% success: range = 26 cells. Junctions at 40-50 cells. UNREACHABLE.
- 5000 steps, 34% success: range = 41 cells. BARELY reachable.
- 5000 steps, 50% success (learned): range = 50 cells. REACHABLE.

Longer episodes give agents enough time to accidentally reach junctions via random
walk, providing the first gradient signal for learning directed navigation.

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
        weight=20.0,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=10.0,
    )
    rewards["wrong_gear_penalty_scrambler"] = reward(
        stat("scrambler.gained"),
        weight=-5.0,
    )
    rewards["wrong_gear_penalty_miner"] = reward(
        stat("miner.gained"),
        weight=-5.0,
    )
    rewards["wrong_gear_penalty_scout"] = reward(
        stat("scout.gained"),
        weight=-5.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=2.0,
    )
    agent_cfg.rewards = rewards
