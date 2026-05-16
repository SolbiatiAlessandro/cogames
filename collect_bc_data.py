"""Collect behavioral cloning data from scripted aligner agent.

Runs the MachinaRolesPolicy on the competition map and records
(observation, action) pairs for training TutorialPolicyNet.

Output: numpy arrays saved to bc_data/ directory
- obs.npy: observations [N, num_tokens, token_dim]
- actions.npy: action indices [N]
"""
import sys
import os
import numpy as np

sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "src")))

from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant, NoClipsVariant
from mettagrid.simulator.simulator import Simulation
from mettagrid.policy.policy import PolicySpec
from mettagrid.policy.loader import initialize_or_load_policy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface

MAX_STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
NUM_EPISODES = int(sys.argv[2]) if len(sys.argv) > 2 else 10

competition_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_machina_1':
            competition_basic = m
            break

competition_basic.max_steps = MAX_STEPS
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

# Remove change_gear handler for aligner-only gear
for station_name in ["c:scrambler", "c:miner", "c:scout"]:
    if station_name in config.game.objects:
        station = config.game.objects[station_name]
        if "change_gear" in station.on_use_handlers:
            del station.on_use_handlers["change_gear"]

env_interface = PolicyEnvInterface.from_mg_cfg(config)

# Load scripted expert policy
expert_spec = PolicySpec(
    class_path="cogames.policy.machina_roles_policy.MachinaRolesPolicy",
    kwargs={"num_aligners": 8, "aligner_ids": "0,1,2,3,4,5,6,7"},
)
expert_policy = initialize_or_load_policy(env_interface, expert_spec)

# Map expert action names to tutorial policy action indices (5-action space)
move_action_map = {
    "noop": 0,
    "move_north": 1,
    "move_south": 2,
    "move_west": 3,
    "move_east": 4,
}

obs_shape = env_interface.observation_space.shape
num_agents = config.game.num_agents

print(f"Observation shape: {obs_shape}")
print(f"Agents: {num_agents}")
print(f"Steps: {MAX_STEPS}, Episodes: {NUM_EPISODES}")
print(f"Expected samples: ~{MAX_STEPS * num_agents * NUM_EPISODES}")

all_obs = []
all_actions = []
total_aligned = 0

for ep in range(NUM_EPISODES):
    sim = Simulation(config, seed=42 + ep)
    expert_policy.reset()

    agents = sim.agents()
    ep_samples = 0

    for step in range(MAX_STEPS):
        if sim.is_done():
            break

        for i, agent in enumerate(agents):
            obs = agent.observation

            # Convert observation to numpy array (same format as PufferEnv)
            obs_array = np.full(obs_shape, 255, dtype=np.uint8)
            for j, token in enumerate(obs.tokens[:obs_shape[0]]):
                obs_array[j, 0] = token.raw_token[0]
                obs_array[j, 1] = token.raw_token[1]
                if obs_shape[1] > 2:
                    obs_array[j, 2] = token.raw_token[2]

            # Get expert action
            agent_policy = expert_policy.agent_policy(i)
            action = agent_policy.step(obs)
            action_name = action.name if hasattr(action, 'name') else str(action)

            # Map to 5-action space
            action_idx = move_action_map.get(action_name, 0)

            all_obs.append(obs_array)
            all_actions.append(action_idx)
            ep_samples += 1

            agent.set_action(action)

        sim.step()

    stats = sim.episode_stats
    aligned = 0
    for k, v in stats.items():
        if 'aligned.junction' in k.lower() and 'held' in k.lower() and 'cogs' in k.lower():
            aligned = v
    total_aligned += aligned

    print(f"Episode {ep+1}/{NUM_EPISODES}: {ep_samples} samples, aligned.junction.held={aligned:.1f}")
    sim.close()

obs_array = np.array(all_obs, dtype=np.uint8)
actions_array = np.array(all_actions, dtype=np.int64)

os.makedirs("bc_data", exist_ok=True)
np.save("bc_data/obs.npy", obs_array)
np.save("bc_data/actions.npy", actions_array)

print(f"\nSaved {len(all_obs)} samples to bc_data/")
print(f"  obs.npy: {obs_array.shape}")
print(f"  actions.npy: {actions_array.shape}")
print(f"  Total aligned junctions: {total_aligned:.1f}")
print(f"  Action distribution: {dict(zip(*np.unique(actions_array, return_counts=True)))}")
