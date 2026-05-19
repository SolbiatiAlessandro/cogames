"""Evaluate an RL checkpoint at multiple step counts.

Usage:
    python scripts/eval_multi_steps.py --checkpoint ./train_dir_.../model_000010.pt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cogames.cli.mission import get_mission
from mettagrid import MettaGridConfig, PufferMettaGridEnv
from mettagrid.envs.stats_tracker import StatsTracker
from mettagrid.mapgen.mapgen import MapGen
from mettagrid.policy.loader import initialize_or_load_policy, resolve_policy_class_path
from mettagrid.policy.policy import PolicySpec
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Simulator
from mettagrid.util.stats_writer import NoopStatsWriter


def eval_checkpoint(checkpoint_path: str, step_counts: list[int], episodes: int = 5,
                    cogs: int = 8, seed: int = 100, temp: float = 0.7):
    policy_class = resolve_policy_class_path("tutorial")

    results = {}
    for max_steps in step_counts:
        _, env_cfg, _ = get_mission(
            "cogsguard_machina_1.basic",
            variants_arg=["no_vibes"],
            cogs=cogs,
        )
        env_cfg.game.max_steps = max_steps

        ep_rewards = []
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
                actions = []
                for agent_id in range(cogs):
                    agent_policy = policy.agent_policy(agent_id)
                    action = agent_policy.step(env.last_obs(agent_id))
                    action_idx = policy_env_info.action_names.index(action.name)
                    actions.append(action_idx)

                obs, reward, terminated, truncated, info = env.step(actions)
                total_reward += sum(reward) if hasattr(reward, '__iter__') else reward
                done = terminated or truncated
                step += 1

            per_agent = total_reward / cogs
            ep_rewards.append(per_agent)

        avg = sum(ep_rewards) / len(ep_rewards)
        peak = max(ep_rewards)
        results[max_steps] = {"avg": avg, "peak": peak, "all": ep_rewards}
        print(f"  {max_steps:>5} steps: avg={avg:.4f}, peak={peak:.4f} ({episodes} episodes)")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--steps", default="500,1000,2000,10000", help="Comma-separated step counts")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--cogs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=100)
    args = parser.parse_args()

    step_counts = [int(s) for s in args.steps.split(",")]
    print(f"Evaluating: {args.checkpoint}")
    eval_checkpoint(args.checkpoint, step_counts, args.episodes, args.cogs, args.seed)


if __name__ == "__main__":
    main()
