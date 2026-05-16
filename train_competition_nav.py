"""Competition map, FIXED seed 42, NO CLIPS, SHORT episodes — navigation curriculum.

Phase 1 of curriculum: teach agents to MOVE without hitting walls.
- 300-step episodes = 6.7x more episodes than 2000-step = faster gradient updates
- Heavy reward for successful moves, penalty for wall bumps
- Exploration bonus to prevent standing still
- Aligner gear bonus to learn gear pickup nearby
- Small alignment bonus (will rarely fire but provides direction)

Once agents learn navigation (move.failed < 30%), fine-tune with full 2000-step config.

Use with: COGAMES_ENT_START=0.15 COGAMES_ENT_END=0.03 COGAMES_ENT_ANNEAL_EPOCHS=20
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

competition_basic.max_steps = 300
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
    rewards["move_success"] = reward(
        stat("action.move.success"),
        weight=0.02,
    )
    rewards["move_failed_penalty"] = reward(
        stat("action.move.failed"),
        weight=-0.01,
    )
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.1,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=5.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=1.0,
    )
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=10.0,
    )
    agent_cfg.rewards = rewards
