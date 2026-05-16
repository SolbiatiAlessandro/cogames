"""Competition map, FIXED seed 42, NO CLIPS, 1 AGENT — simplest alignment problem.

Why 1 agent: eliminates multi-agent credit assignment. ALL reward belongs to
the single agent. The LSTM only needs to learn "my position → go this way."

Key settings:
- 1 agent, 2000 steps, no clips (aligned junctions stay aligned)
- Strong exploration to force map coverage (13x13 obs on 88x88 map)
- Move success/failure rewards for wall avoidance
- Aligner gear bonus to learn station interaction
- High alignment bonus for the rare junction alignment event

Once 1-agent learns, scale to 8 agents (same policy, deployed independently).

Use with: COGAMES_ENT_START=0.05 COGAMES_ENT_END=0.01 COGAMES_ENT_ANNEAL_EPOCHS=40
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

competition_basic.max_steps = 2000
competition_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=1, wealth=1, initial_hearts=15),
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
    rewards["move_success"] = reward(
        stat("action.move.success"),
        weight=0.01,
    )
    rewards["move_failed_penalty"] = reward(
        stat("action.move.failed"),
        weight=-0.005,
    )
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.05,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=10.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=2.0,
    )
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=20.0,
    )
    agent_cfg.rewards = rewards
