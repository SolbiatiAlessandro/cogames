"""V13: BC-initialized RL on 50x50 arena map.

Combines two advantages:
1. BC initialization gives directional movement bias from expert
2. Arena map (50x50) gives denser junctions and shorter distances

The 50x50 arena has 53 junctions, hub is centered, and nearly the entire
map is within HUB_ALIGN_DISTANCE=25. This means ANY random walk that reaches
a junction will trigger alignment if the agent has gear+heart.

Uses lower LR (3e-4) and gentle entropy for fine-tuning from BC.

env var COGAMES_BC_INIT=path/to/bc_best.pt to specify BC weights.
(Note: BC was trained on 88x88 machina_1, but obs shape is same 13x13 window)
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant, NoClipsVariant

from mettagrid.config.game_value import stat
from mettagrid.config.reward_config import reward

arena_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_arena':
            arena_basic = m
            break

if arena_basic is None:
    raise ValueError("Could not find cogsguard_arena.basic mission")

arena_basic.max_steps = 2000
arena_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=200),
}

no_vibes = NoVibesVariant()
no_clips = NoClipsVariant()
arena_basic.variants = list(getattr(arena_basic, 'variants', []))
arena_basic.variants.append(no_vibes)
arena_basic.variants.append(no_clips)

config = arena_basic.make_env()

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
