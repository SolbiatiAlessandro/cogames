"""Evaluate an RL checkpoint on the competition mission.

Usage:
    source .venv/bin/activate
    python scripts/eval_rl_checkpoint.py --checkpoint ./train_dir_custom/<run_id>/model_000010.pt [--steps 1000] [--episodes 5]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cogames.cli.mission import get_mission
from mettagrid import MettaGridConfig, PufferMettaGridEnv
from mettagrid.envs.stats_tracker import StatsTracker
from mettagrid.mapgen.mapgen import MapGen
from mettagrid.policy.loader import initialize_or_load_policy
from mettagrid.policy.policy import PolicySpec
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Simulator
from mettagrid.util.stats_writer import NoopStatsWriter


def run_eval(env_cfg: MettaGridConfig, policy_class: str, checkpoint_path: str, episodes: int, seed: int):
    results = []

    for ep in range(episodes):
        map_builder = getattr(env_cfg.game, "map_builder", None)
        if isinstance(map_builder, MapGen.Config):
            map_builder.seed = seed + ep

        simulator = Simulator()
        stats_tracker = StatsTracker(NoopStatsWriter())
        simulator.add_event_handler(stats_tracker)

        cfg_copy = env_cfg.model_copy(deep=True)
        env = PufferMettaGridEnv(simulator, cfg_copy, seed=seed + ep)

        policy_env_info = PolicyEnvInterface.from_mg_cfg(cfg_copy)
        policy = initialize_or_load_policy(
            policy_env_info,
            PolicySpec(class_path=policy_class, data_path=checkpoint_path),
        )

        obs, _ = env.reset()
        done = False
        total_reward = 0.0
        step = 0

        while not done:
            import torch
            import numpy as np

            obs_tensor = torch.from_numpy(obs).unsqueeze(0) if isinstance(obs, np.ndarray) else obs
            actions = []
            for agent_id in range(env_cfg.game.num_agents):
                agent_policy = policy.agent_policy(agent_id)
                action = agent_policy.step(env.last_obs(agent_id))
                action_idx = policy_env_info.action_names.index(action.name)
                actions.append(action_idx)

            obs, reward, terminated, truncated, info = env.step(actions)
            total_reward += sum(reward) if hasattr(reward, '__iter__') else reward
            done = terminated or truncated
            step += 1

        per_agent_reward = total_reward / env_cfg.game.num_agents
        stats = {}
        if hasattr(stats_tracker, '_stats'):
            stats = dict(stats_tracker._stats)

        results.append({
            "episode": ep,
            "total_reward": total_reward,
            "per_agent_reward": per_agent_reward,
            "steps": step,
        })
        print(f"Episode {ep}: total_reward={total_reward:.4f}, per_agent={per_agent_reward:.4f}, steps={step}")

    avg_reward = sum(r["per_agent_reward"] for r in results) / len(results)
    print(f"\nAverage per-agent reward over {episodes} episodes: {avg_reward:.4f}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate RL checkpoint")
    parser.add_argument("--checkpoint", required=True, help="Path to model checkpoint")
    parser.add_argument("--policy-class", default="tutorial", help="Policy class name")
    parser.add_argument("--mission", default="cogsguard_machina_1.basic", help="Mission to evaluate on")
    parser.add_argument("--cogs", type=int, default=8, help="Number of agents")
    parser.add_argument("--steps", type=int, default=1000, help="Steps per episode")
    parser.add_argument("--episodes", type=int, default=5, help="Number of evaluation episodes")
    parser.add_argument("--seed", type=int, default=100, help="Eval seed (different from training)")
    parser.add_argument("--no-vibes", action="store_true", default=True, help="Use no_vibes variant")
    args = parser.parse_args()

    variants = ["no_vibes"] if args.no_vibes else []
    _, env_cfg, _ = get_mission(
        args.mission,
        variants_arg=variants if variants else None,
        cogs=args.cogs,
    )
    env_cfg.game.max_steps = args.steps

    from mettagrid.policy.loader import resolve_policy_class_path
    policy_class = resolve_policy_class_path(args.policy_class)

    print(f"Evaluating: {args.checkpoint}")
    print(f"Mission: {args.mission}, steps={args.steps}, cogs={args.cogs}, episodes={args.episodes}")
    print()

    run_eval(env_cfg, policy_class, args.checkpoint, args.episodes, args.seed)


if __name__ == "__main__":
    main()
