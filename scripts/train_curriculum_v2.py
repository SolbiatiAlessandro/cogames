"""Curriculum RL training for competition map — Phase 1/2/3.

Trains LSTM policy on competition-like maps with progressively harder junction placement.
Phase 1: High junction density (building_coverage=0.3) — junctions very close to hub
Phase 2: Medium density (building_coverage=0.15) — junctions at medium distance
Phase 3: Default density (building_coverage=0.05) — full competition setting

Uses the installed cogames API (no source modifications needed).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import torch

from cogames.cli.mission import get_mission
from cogames.train import train
from mettagrid.policy.loader import resolve_policy_class_path


def modify_env_for_curriculum(env_cfg, phase, building_coverage=None, no_clips=False,
                              max_steps=None, increase_junctions=False):
    """Modify environment config for curriculum training."""
    mb = env_cfg.game.map_builder
    inst_dict = mb.model_dump()['instance']

    if building_coverage is not None:
        mb.instance.building_coverage = building_coverage
        print(f"  Set building_coverage={building_coverage}")

    if increase_junctions:
        weights = mb.instance.building_weights
        if isinstance(weights, dict):
            weights['junction'] = 1.0
            mb.instance.building_weights = weights
            print(f"  Boosted junction weight to 1.0")

    if no_clips:
        mb.instance.map_corner_placements = []
        print(f"  Removed clips ships")

    if max_steps is not None:
        env_cfg.game.max_steps = max_steps
        print(f"  Set max_steps={max_steps}")


def main():
    parser = argparse.ArgumentParser(description="Curriculum RL training v2")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2, 3])
    parser.add_argument("--steps", type=int, default=2000000)
    parser.add_argument("--cogs", type=int, default=4)
    parser.add_argument("--weights", default=None, help="Initial weights checkpoint")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mission", default="arena", help="Base mission")
    parser.add_argument("--max-steps", type=int, default=1000, help="Episode max steps")
    parser.add_argument("--num-envs", type=int, default=16)
    parser.add_argument("--checkpoint-interval", type=int, default=10)
    parser.add_argument("--tag", default="")
    parser.add_argument("--no-clips", action="store_true", default=True)
    parser.add_argument("--building-coverage", type=float, default=None)
    parser.add_argument("--increase-junctions", action="store_true", default=False)
    parser.add_argument("--policy-class", default="mettagrid.policy.lstm.LSTMPolicy")
    args = parser.parse_args()

    phase_config = {
        1: {"building_coverage": 0.30, "desc": "High junction density (close junctions)"},
        2: {"building_coverage": 0.15, "desc": "Medium junction density"},
        3: {"building_coverage": 0.05, "desc": "Default (competition) junction density"},
    }

    phase = phase_config[args.phase]
    bc = args.building_coverage if args.building_coverage is not None else phase["building_coverage"]

    print(f"=== CURRICULUM PHASE {args.phase}: {phase['desc']} ===")
    print(f"  building_coverage: {bc}")
    print(f"  steps: {args.steps}")
    print(f"  mission: {args.mission}")
    print(f"  initial weights: {args.weights or 'random'}")
    print(f"  max_steps: {args.max_steps}")

    variants = ["no_vibes"]
    if args.no_clips:
        variants.append("no_clips")

    _, env_cfg, _ = get_mission(args.mission, variants_arg=variants, cogs=args.cogs)

    modify_env_for_curriculum(
        env_cfg,
        args.phase,
        building_coverage=bc,
        no_clips=False,
        max_steps=args.max_steps,
        increase_junctions=args.increase_junctions,
    )

    policy_class_path = resolve_policy_class_path(args.policy_class)
    if policy_class_path == args.policy_class:
        pass

    tag = f"_{args.tag}" if args.tag else ""
    checkpoint_dir = Path(f"./train_dir_curriculum_p{args.phase}{tag}")

    print(f"  checkpoint_dir: {checkpoint_dir}")
    print(f"  policy_class: {policy_class_path}")
    print()

    start_time = time.time()

    train(
        env_cfg=env_cfg,
        policy_class_path=policy_class_path,
        initial_weights_path=args.weights,
        device=torch.device("cpu"),
        num_steps=args.steps,
        checkpoints_path=checkpoint_dir,
        seed=args.seed,
        map_seed=args.seed,
        minibatch_size=4096,
        vector_num_envs=args.num_envs,
        log_outputs=True,
        checkpoint_interval=args.checkpoint_interval,
    )

    elapsed = time.time() - start_time
    print(f"\nTraining completed in {elapsed:.0f}s")
    print(f"Checkpoints in: {checkpoint_dir}")


if __name__ == "__main__":
    main()
