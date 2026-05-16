"""V6: V4 rewards + massive hearts (200) to keep agents alive for 2500+ steps.

V4 achieved max_steps=58 but 0 alignment. Agents die from HP depletion (50 HP,
-1/tick, ~2 hearts each from hub) before reaching distant junctions.

With initial_hearts=200, each agent can pick up ~25 hearts = ~2500+ ticks alive.
This gives agents enough time to randomly reach junctions through exploration.
Also increase initial_hp to 100 (max cap) so agents start at full health.

Same V4 reward structure (alignment=50.0, aligner_gained=15.0, no penalties).
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

apply_reward_variants(config, variants=["milestones_2:25", "credit"])

for agent_cfg in config.game.agents:
    agent_cfg.inventory.initial["hp"] = 100

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
