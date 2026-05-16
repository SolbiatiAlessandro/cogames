"""Quick evaluation of BC-pretrained policy on competition/arena maps.

Uses the mettagrid Simulator directly for faster eval than cogames scrimmage.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import torch
from cogames.cli.mission import get_mission
from cogames.policy.tutorial_policy import TutorialPolicyNet
from mettagrid.mapgen.mapgen import MapGen
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action, Simulator


def obs_to_tensor(agent_obs, policy_env_info):
    num_tokens, token_dim = policy_env_info.observation_space.shape
    obs_array = np.full((num_tokens, token_dim), 255, dtype=np.uint8)
    for i, token in enumerate(agent_obs.tokens[:num_tokens]):
        obs_array[i, : len(token.raw_token)] = token.raw_token
    return torch.from_numpy(obs_array)


def run_episode(env_cfg, net, policy_env_info, seed, max_steps=500):
    cfg_copy = env_cfg.model_copy(deep=True)
    map_builder = getattr(cfg_copy.game, "map_builder", None)
    if isinstance(map_builder, MapGen.Config):
        map_builder.seed = seed

    simulator = Simulator()
    sim = simulator.new_simulation(cfg_copy, seed)
    agents = sim.agents()
    num_agents = len(agents)

    action_names = policy_env_info.action_names
    lstm_h = torch.zeros(1, 1, net.hidden_size)
    lstm_c = torch.zeros(1, 1, net.hidden_size)
    agent_states = [(lstm_h.clone(), lstm_c.clone()) for _ in range(num_agents)]

    step = 0
    action_counts = {name: 0 for name in action_names}

    while not sim.is_done() and step < max_steps:
        for i in range(num_agents):
            obs = agents[i].observation
            obs_tensor = obs_to_tensor(obs, policy_env_info).float().unsqueeze(0)

            with torch.no_grad():
                h, c = agent_states[i]
                logits, _ = net(obs_tensor, (h, c))
                probs = torch.softmax(logits, dim=-1)
                action_idx = torch.argmax(probs, dim=-1).item()

            action_name = action_names[action_idx]
            action_counts[action_name] += 1
            action = Action(action_name)
            agents[i].set_action(action)

        sim.step()
        step += 1

    stats = {}
    for agent in agents:
        for key, val in agent.stats.items():
            if key not in stats:
                stats[key] = 0
            stats[key] += val

    return step, stats, action_counts, num_agents


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True, help="BC weights path")
    parser.add_argument("--mission", default="cogsguard_arena.basic")
    parser.add_argument("--cogs", type=int, default=8)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--no-vibes", action="store_true", default=True)
    args = parser.parse_args()

    variants = ["no_vibes"] if args.no_vibes else []
    _, env_cfg, _ = get_mission(
        args.mission,
        variants_arg=variants if variants else None,
        cogs=args.cogs,
    )
    env_cfg.game.max_steps = args.steps

    policy_env_info = PolicyEnvInterface.from_mg_cfg(env_cfg)
    print(f"Action names: {policy_env_info.action_names}")
    print(f"Obs space: {policy_env_info.observation_space}")

    net = TutorialPolicyNet(policy_env_info)
    state_dict = torch.load(args.weights, map_location="cpu", weights_only=True)
    net.load_state_dict(state_dict)
    net.eval()
    print(f"Loaded weights from {args.weights}")
    print(f"Evaluating on {args.mission}, {args.cogs} agents, {args.steps} steps, {args.episodes} episodes\n")

    all_stats = {}
    for ep in range(args.episodes):
        step, stats, action_counts, num_agents = run_episode(
            env_cfg, net, policy_env_info, args.seed + ep, args.steps
        )
        print(f"Episode {ep} ({step} steps):")
        print(f"  Actions: {action_counts}")

        key_stats = [
            "aligned.junction.held", "aligned.junction", "heart.gained", "heart.amount",
            "cell.visited", "action.move.failed", "carbon.deposited", "oxygen.deposited",
            "germanium.deposited", "silicon.deposited",
        ]
        for k in key_stats:
            v = stats.get(k, 0)
            if k not in all_stats:
                all_stats[k] = []
            all_stats[k].append(v / num_agents)
            print(f"  {k}: {v} (per-agent: {v/num_agents:.2f})")

        other_stats = {k: v for k, v in sorted(stats.items()) if k not in key_stats and v > 0}
        if other_stats:
            print(f"  Other non-zero stats: {other_stats}")
        print()

    print("=== AVERAGES (per agent) ===")
    for k, vals in all_stats.items():
        avg = sum(vals) / len(vals)
        print(f"  {k}: {avg:.3f}")


if __name__ == "__main__":
    main()
