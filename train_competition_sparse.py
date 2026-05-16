"""Competition map: 5-action, 15 hearts, 1000 steps, SPARSE alignment-focused reward.

Previous configs had too-dominant hub interaction rewards (mining, hearts, deposits)
that kept agents near the hub. The agent never learns to navigate to junctions because
hub activities are more rewarding than exploring.

This config minimizes hub shaping and focuses on alignment-related rewards:
- Keeps milestones_2 for the objective (aligned_junction_held per-tick)
- Removes credit (dense hub interaction rewards)
- Adds junction_aligned_by_agent with HIGH weight
- Keeps cell.visited for exploration incentive
"""
from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant

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

competition_basic.max_steps = 1000

competition_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

no_vibes = NoVibesVariant()
competition_basic.variants = list(getattr(competition_basic, 'variants', []))
competition_basic.variants.append(no_vibes)

config = competition_basic.make_env()

# Only milestones_2 (NOT credit) — focus on objective, not hub interactions
apply_reward_variants(config, variants=["milestones_2"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    # Strong junction alignment reward
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=5.0,
    )
    # Exploration reward to leave hub area
    rewards["exploration_bonus"] = reward(
        stat("cell.visited"),
        weight=0.005,
    )
    # Small aligner gear reward (just enough to guide gear acquisition)
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=0.5,
    )
    agent_cfg.rewards = rewards
