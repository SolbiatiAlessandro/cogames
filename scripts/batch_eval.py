#!/usr/bin/env python3
"""Batch evaluate multiple RL checkpoints at multiple step lengths.

Usage:
  python scripts/batch_eval.py train_dir_p2*/*/model_*.pt --steps 500 1000 5000 10000 --episodes 3
  python scripts/batch_eval.py train_dir_p1*/*/model_000050.pt --steps 500 --episodes 5 --mission cogsguard_arena.basic
"""
from __future__ import annotations

import argparse
import glob
import re
import subprocess
import sys
from pathlib import Path


def eval_checkpoint(checkpoint: str, mission: str, cogs: int, episodes: int,
                    steps: int, seed: int, variants: list[str], temperature: float = 0.7) -> dict:
    player_cfg = f"class=tutorial,data={checkpoint}"
    if temperature != 1.0:
        player_cfg += f",temperature={temperature}"
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

    # Parse per-episode avg rewards from the table
    rewards = []
    for line in output.split("\n"):
        match = re.search(r"│\s+\d+\s+│\s+([\d.]+)\s+│", line)
        if match:
            rewards.append(float(match.group(1)))

    # Parse game stats
    junction_held = 0.0
    for line in output.split("\n"):
        if "cogs/aligned.junction.held" in line:
            match = re.search(r"([\d.]+)\s+│\s*$", line)
            if match:
                junction_held = float(match.group(1))

    avg = sum(rewards) / len(rewards) if rewards else 0.0
    peak = max(rewards) if rewards else 0.0
    return {
        "avg": avg,
        "peak": peak,
        "rewards": rewards,
        "junction_held": junction_held,
        "success": len(rewards) > 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoints", nargs="+", help="Checkpoint paths (glob patterns ok)")
    parser.add_argument("--steps", type=int, nargs="+", default=[500, 10000])
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--cogs", type=int, default=8)
    parser.add_argument("--mission", type=str, default="cogsguard_machina_1.basic")
    parser.add_argument("--seed", type=int, default=3000)
    parser.add_argument("--variant", type=str, nargs="*", default=["no_vibes"])
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args()

    # Expand globs
    all_checkpoints = []
    for pattern in args.checkpoints:
        expanded = sorted(glob.glob(pattern))
        all_checkpoints.extend(expanded)

    if not all_checkpoints:
        print("No checkpoints found!")
        sys.exit(1)

    print(f"Evaluating {len(all_checkpoints)} checkpoints at {args.steps} steps")
    print(f"Mission: {args.mission}, Cogs: {args.cogs}, Episodes: {args.episodes}")
    print()

    # Print header
    header = f"{'Checkpoint':<50}"
    for s in args.steps:
        header += f"  {'avg@'+str(s):>10}  {'peak@'+str(s):>10}  {'jh@'+str(s):>8}"
    print(header)
    print("-" * len(header))

    for cp in all_checkpoints:
        cp_name = Path(cp).stem
        parent = Path(cp).parent.parent.name
        label = f"{parent}/{cp_name}"
        row = f"{label:<50}"

        for s in args.steps:
            result = eval_checkpoint(cp, args.mission, args.cogs, args.episodes,
                                     s, args.seed, args.variant, temperature=args.temperature)
            if result["success"]:
                row += f"  {result['avg']:>10.4f}  {result['peak']:>10.4f}  {result['junction_held']:>8.0f}"
            else:
                row += f"  {'FAIL':>10}  {'FAIL':>10}  {'FAIL':>8}"

        print(row)


if __name__ == "__main__":
    main()
