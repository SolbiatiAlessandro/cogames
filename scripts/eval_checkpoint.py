#!/usr/bin/env python3
"""Evaluate an RL checkpoint on the competition map.

Usage:
  python scripts/eval_checkpoint.py <checkpoint_path> --steps 500 --episodes 5
  python scripts/eval_checkpoint.py <checkpoint_path> --steps 10000 --episodes 3
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np

from cogames.evaluate import evaluate
from mettagrid.policy.policy import PolicySpec

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("eval_checkpoint")


def main():
    parser = argparse.ArgumentParser(description="Evaluate RL checkpoint")
    parser.add_argument("checkpoint", type=str, help="Path to checkpoint .pt file")
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--cogs", type=int, default=8, help="Number of agents (8 for competition)")
    parser.add_argument("--mission", type=str, default="cogsguard_machina_1.basic")
    parser.add_argument("--seed", type=int, default=3000)
    parser.add_argument("--no-vibes", action="store_true", default=True)
    parser.add_argument("--temp", type=float, default=0.7)

    args = parser.parse_args()

    policy_spec = PolicySpec(
        class_path="cogames.policy.tutorial_policy.TutorialPolicy",
        data_path=args.checkpoint,
    )

    variants = []
    if args.no_vibes:
        variants.append("no_vibes")

    rewards_per_episode = []
    stats_per_episode = []

    for ep in range(args.episodes):
        seed = args.seed + ep
        logger.info(f"Episode {ep+1}/{args.episodes} (seed={seed}, steps={args.steps})")

        from cogames.cogs_vs_clips.missions import get_mission_config
        env_cfg = get_mission_config(
            args.mission,
            cogs=args.cogs,
            variants=variants if variants else None,
        )
        env_cfg.game.max_steps = args.steps

        result = evaluate(
            env_cfg=env_cfg,
            policies=[(policy_spec, 1.0)],
            num_episodes=1,
            seed=seed,
        )

        if result and len(result) > 0:
            ep_result = result[0]
            mission_reward = ep_result.get("mission_reward", 0.0)
            rewards_per_episode.append(mission_reward)
            stats_per_episode.append(ep_result)
            logger.info(f"  Reward: {mission_reward:.4f}")

            # Print key stats
            for key in ["aligned.junction.held", "heart.gained", "aligner.gained",
                         "junction.aligned_by_agent", "carbon.deposited"]:
                val = ep_result.get(key, "N/A")
                if val != "N/A":
                    logger.info(f"  {key}: {val}")
        else:
            logger.warning(f"  No result for episode {ep+1}")
            rewards_per_episode.append(0.0)

    if rewards_per_episode:
        avg = np.mean(rewards_per_episode)
        std = np.std(rewards_per_episode)
        peak = np.max(rewards_per_episode)
        median = np.median(rewards_per_episode)
        logger.info(f"\n=== SUMMARY ({args.episodes} episodes, {args.steps} steps) ===")
        logger.info(f"  Avg:    {avg:.4f}")
        logger.info(f"  Std:    {std:.4f}")
        logger.info(f"  Peak:   {peak:.4f}")
        logger.info(f"  Median: {median:.4f}")
        logger.info(f"  All:    {[f'{r:.4f}' for r in rewards_per_episode]}")


if __name__ == "__main__":
    main()
