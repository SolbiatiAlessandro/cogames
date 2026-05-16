"""Collect (observation, action) demonstration pairs from the scripted policy.

Uses the mettagrid Simulator/Rollout directly to get proper per-agent
observations in the format the policies expect.

Usage:
    source .venv/bin/activate
    python scripts/collect_demonstrations.py --episodes 10 --output demos_arena.pt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import torch
from cogames.cli.mission import get_mission
from mettagrid.mapgen.mapgen import MapGen
from mettagrid.policy.loader import initialize_or_load_policy
from mettagrid.policy.policy import PolicySpec
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Simulator


def obs_to_tensor(agent_obs, policy_env_info):
    """Convert AgentObservation to tensor [200, 3] matching PufferLib format."""
    num_tokens, token_dim = policy_env_info.observation_space.shape
    obs_array = np.full((num_tokens, token_dim), 255, dtype=np.uint8)
    for i, token in enumerate(agent_obs.tokens[:num_tokens]):
        obs_array[i, : len(token.raw_token)] = token.raw_token
    return torch.from_numpy(obs_array)


def collect_episode(env_cfg, policy_class, policy_data, seed, policy_env_info):
    cfg_copy = env_cfg.model_copy(deep=True)
    map_builder = getattr(cfg_copy.game, "map_builder", None)
    if isinstance(map_builder, MapGen.Config):
        map_builder.seed = seed

    simulator = Simulator()
    sim = simulator.new_simulation(cfg_copy, seed)
    agents = sim.agents()
    num_agents = len(agents)

    policy = initialize_or_load_policy(
        policy_env_info,
        PolicySpec(class_path=policy_class, data_path=policy_data),
    )
    agent_policies = [policy.agent_policy(i) for i in range(num_agents)]
    for p in [policy]:
        p.reset()

    action_names = policy_env_info.action_names
    all_obs = []
    all_actions = []
    step_count = 0

    while not sim.is_done():
        step_obs = []
        step_actions = []

        for i in range(num_agents):
            obs = agents[i].observation
            action = agent_policies[i].step(obs)
            agents[i].set_action(action)

            obs_tensor = obs_to_tensor(obs, policy_env_info)
            action_idx = action_names.index(action.name)

            step_obs.append(obs_tensor)
            step_actions.append(action_idx)

        sim.step()
        step_count += 1

        all_obs.append(torch.stack(step_obs))
        all_actions.append(torch.tensor(step_actions, dtype=torch.long))

    return all_obs, all_actions, step_count


def main():
    parser = argparse.ArgumentParser(description="Collect demonstrations from scripted policy")
    parser.add_argument("--mission", default="cogsguard_arena.basic", help="Mission")
    parser.add_argument("--policy", default="machina_roles", help="Policy class")
    parser.add_argument("--policy-data", default=None, help="Policy data path")
    parser.add_argument("--cogs", type=int, default=8, help="Number of agents")
    parser.add_argument("--episodes", type=int, default=10, help="Number of episodes")
    parser.add_argument("--steps", type=int, default=500, help="Max steps per episode")
    parser.add_argument("--output", default="demos_arena.pt", help="Output file")
    parser.add_argument("--seed", type=int, default=42, help="Starting seed")
    args = parser.parse_args()

    _, env_cfg, _ = get_mission(args.mission, cogs=args.cogs)
    env_cfg.game.max_steps = args.steps

    from mettagrid.policy.loader import resolve_policy_class_path
    policy_class = resolve_policy_class_path(args.policy)

    policy_env_info = PolicyEnvInterface.from_mg_cfg(env_cfg)
    action_names = policy_env_info.action_names
    print(f"Action names: {action_names}")
    print(f"Observation space: {policy_env_info.observation_space}")
    print(f"Collecting {args.episodes} episodes from {args.policy} on {args.mission}")
    print()

    total_obs = []
    total_actions = []
    total_steps = 0

    for ep in range(args.episodes):
        obs_list, action_list, steps = collect_episode(
            env_cfg, policy_class, args.policy_data, args.seed + ep, policy_env_info
        )
        total_obs.extend(obs_list)
        total_actions.extend(action_list)
        total_steps += steps
        print(f"Episode {ep}: {steps} steps, total {total_steps} steps so far")

    obs_tensor = torch.stack(total_obs)
    action_tensor = torch.stack(total_actions)

    demo_data = {
        "observations": obs_tensor,
        "actions": action_tensor,
        "action_names": action_names,
        "num_agents": args.cogs,
        "mission": args.mission,
        "policy": args.policy,
        "episodes": args.episodes,
        "total_steps": total_steps,
    }

    torch.save(demo_data, args.output)
    print(f"\nSaved {total_steps} timesteps x {args.cogs} agents to {args.output}")
    print(f"Obs shape: {obs_tensor.shape}, Actions shape: {action_tensor.shape}")


if __name__ == "__main__":
    main()
