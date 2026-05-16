"""V12: BC-initialized RL on 88x88 map.

Strategy: Initialize from behavioral cloning weights that learned movement
patterns from the scripted agent, then fine-tune with RL rewards.

BC provides: directional movement bias (south/west/east), basic exploration
RL provides: alignment reward signal to refine navigation toward junctions

Uses lower learning rate (3e-4) and slower entropy annealing to avoid
destroying the BC initialization too quickly.

env var COGAMES_BC_INIT=path/to/bc_best.pt to specify BC weights.
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
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=200),
}

no_vibes = NoVibesVariant()
no_clips = NoClipsVariant()
competition_basic.variants = list(getattr(competition_basic, 'variants', []))
competition_basic.variants.append(no_vibes)
competition_basic.variants.append(no_clips)

config = competition_basic.make_env()

config.game.map_builder.seed = 42

# Remove change_gear handler from non-aligner stations (aligner-only gear)
for station_name in ["c:scrambler", "c:miner", "c:scout"]:
    if station_name in config.game.objects:
        station = config.game.objects[station_name]
        if "change_gear" in station.on_use_handlers:
            del station.on_use_handlers["change_gear"]

apply_reward_variants(config, variants=["milestones_2:25", "credit"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.5,
        max=100.0,
    )
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=200.0,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=30.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=5.0,
    )
    agent_cfg.rewards = rewards
