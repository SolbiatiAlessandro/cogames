#!/usr/bin/env python3
"""Evaluate an RL checkpoint on the competition map.

Runs cogames CLI evaluation and parses output for reward metrics.

Usage:
  python scripts/eval_checkpoint.py <checkpoint_path>
  python scripts/eval_checkpoint.py <checkpoint_path> --steps 10000 --episodes 3 --cogs 8
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys


def run_eval(checkpoint: str, mission: str, cogs: int, episodes: int,
             steps: int, seed: int, variants: list[str], temperature: float = 1.0) -> dict:
    player_cfg = f"class=tutorial,data={checkpoint}"
    if temperature != 1.0:
        player_cfg += f",kw.temperature={temperature}"
    cmd = [
        sys.executable, "-m", "cogames", "run",
        "-m", mission,
        "-p", player_cfg,
        "-c", str(cogs),
        "-e", str(episodes),
        "-s", str(steps),
        "--seed", str(seed),
    ]
    for v in variants:
        cmd.extend(["-v", v])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    output = result.stdout + result.stderr

    # Parse per-episode rewards from the table
    rewards = []
    for line in output.split("\n"):
        # Match lines like: │ mission_name │       0 │                           0.05 │
        match = re.search(r"│\s+\d+\s+│\s+([\d.]+)\s+│", line)
        if match:
            rewards.append(float(match.group(1)))

    # Parse key stats
    stats = {}
    for line in output.split("\n"):
        match = re.search(r"│\s+\S+\s+│\s+([\w./]+)\s+│\s+([\d.]+)\s+│", line)
        if match:
            stats[match.group(1)] = float(match.group(2))

    return {
        "rewards": rewards,
        "stats": stats,
        "avg_reward": sum(rewards) / len(rewards) if rewards else 0.0,
        "peak_reward": max(rewards) if rewards else 0.0,
        "raw_output": output,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate RL checkpoint")
    parser.add_argument("checkpoint", type=str)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--cogs", type=int, default=8)
    parser.add_argument("--mission", type=str, default="cogsguard_machina_1.basic")
    parser.add_argument("--seed", type=int, default=3000)
    parser.add_argument("--variant", type=str, nargs="*", default=["no_vibes"])
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    print(f"Evaluating {args.checkpoint}")
    print(f"  Mission: {args.mission}, Cogs: {args.cogs}, Steps: {args.steps}, Episodes: {args.episodes}")
    print(f"  Temperature: {args.temperature}")

    result = run_eval(
        args.checkpoint, args.mission, args.cogs, args.episodes,
        args.steps, args.seed, args.variant, temperature=args.temperature,
    )

    print(f"\n=== Results ({args.episodes} episodes, {args.steps} steps) ===")
    print(f"  Avg reward:  {result['avg_reward']:.4f}")
    print(f"  Peak reward: {result['peak_reward']:.4f}")
    print(f"  All rewards: {result['rewards']}")

    key_stats = ["cogs/aligned.junction.held", "cogs/aligned.junction",
                 "heart.gained", "aligner.gained", "junction.aligned_by_agent"]
    for k in key_stats:
        if k in result["stats"]:
            print(f"  {k}: {result['stats'][k]:.2f}")

    if args.verbose:
        print("\n=== Full Output ===")
        print(result["raw_output"])


if __name__ == "__main__":
    main()
