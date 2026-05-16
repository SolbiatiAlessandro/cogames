"""Evaluate an RL checkpoint on competition or arena missions.

Usage:
    python scripts/eval_checkpoint_v2.py --checkpoint ./train_dir/run_id/model_000010.pt
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Evaluate RL checkpoint")
    parser.add_argument("--checkpoint", required=True, help="Path to model checkpoint")
    parser.add_argument("--policy-class", default="mettagrid.policy.lstm.LSTMPolicy")
    parser.add_argument("--mission", default="machina_1.clips", help="Mission to evaluate on")
    parser.add_argument("--cogs", type=int, default=8, help="Number of agents")
    parser.add_argument("--steps", type=int, default=500, help="Steps per episode")
    parser.add_argument("--episodes", type=int, default=3, help="Number of episodes")
    parser.add_argument("--seed", type=int, default=100, help="Eval seed")
    args = parser.parse_args()

    cmd = [
        "cogames", "scrimmage",
        "-m", args.mission,
        "-v", "no_vibes",
        "-c", str(args.cogs),
        "-p", f"class={args.policy_class},data={args.checkpoint}",
        "-e", str(args.episodes),
        "-s", str(args.steps),
        "--seed", str(args.seed),
    ]

    print(f"Evaluating: {args.checkpoint}")
    print(f"Mission: {args.mission}, steps={args.steps}, cogs={args.cogs}, episodes={args.episodes}")
    print(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
