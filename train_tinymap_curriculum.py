"""Tiny-map curriculum: 35x35 map forces junctions within observation range.

Key insight: on a 35x35 map with a 21x21 hub, junctions are only 3-7 tiles
from the hub edge. With a 13x13 observation window (±6 tiles), agents at
the hub edge CAN see junctions. This makes alignment learnable without
requiring long-range navigation.

Phase 1: Train on tiny map until alignment is learned
Phase 2: Fine-tune on competition map (transfer navigation skills)

Run with COGAMES_ENT_COEF=0.05 to prevent entropy collapse.
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

arena_basic.max_steps = 1000
arena_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

no_vibes = NoVibesVariant()
no_clips = NoClipsVariant()
arena_basic.variants = list(getattr(arena_basic, 'variants', []))
arena_basic.variants.append(no_vibes)
arena_basic.variants.append(no_clips)

config = arena_basic.make_env()

map_builder = config.game.map_builder
config.game.map_builder = map_builder.model_copy(update={"width": 35, "height": 35})

apply_reward_variants(config, variants=["milestones_2"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=10.0,
    )
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.02,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=2.0,
    )
    rewards["heart_bonus"] = reward(
        stat("heart.gained"),
        weight=0.5,
    )
    agent_cfg.rewards = rewards
