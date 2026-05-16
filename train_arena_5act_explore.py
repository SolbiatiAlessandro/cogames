"""Arena training with 5-action, 15 hearts, exploration reward + high entropy.

The 50x50 arena map places junctions ~7-10 tiles from hub center — within
the 13x13 observation window. Agents can SEE junctions from the hub area,
unlike the 88x88 competition map where junctions are 15+ tiles away.

If agents learn "walk toward visible junction → align it" on arena,
this behavior should transfer to competition map when agents happen to
see junctions during exploration.

Use with COGAMES_ENT_COEF=0.02 for sustained exploration.
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant

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
arena_basic.variants = list(getattr(arena_basic, 'variants', []))
arena_basic.variants.append(no_vibes)

config = arena_basic.make_env()

apply_reward_variants(config, variants=["milestones_2", "aligner"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.05,
    )
    agent_cfg.rewards = rewards
