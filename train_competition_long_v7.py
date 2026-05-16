"""V7: V4 rewards + immortal agents (hp_regen=0).

Agents die at ~58 steps from HP drain (hp_regen=-1). V7 removes HP drain
entirely so agents survive all 5000 steps, testing whether alignment failure
is purely a lifespan issue. With 5000 steps alive, agents should visit hundreds
of cells through exploration reward and encounter junctions naturally.

Risk: Without death pressure, no urgency signal. But we need alignment events
to occur AT ALL before we can optimize frequency.
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam, CogConfig
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
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=200),
}
competition_basic.cog = CogConfig(hp_regen=0, initial_hp=100)

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
