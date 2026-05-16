"""V11: Train on 50x50 arena map where junctions are closer to hub.

V8-V9 both show alignment fading after ~15 epochs on the 88x88 map.
Root cause: junctions are distance 15-40+ from hub, random walks rarely
reach them, alignment events are too sparse for consistent gradient.

V11 uses the 50x50 CogsGuard arena where hub is centered and junctions
are within 10-20 cells. This should give 3-5x more alignment events,
providing dense enough signal for the policy to learn intentional
junction-seeking behavior.

Same rewards as V9 (alignment=200, exploration=0.5/max100, aligner=30).
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
