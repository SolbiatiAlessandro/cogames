#!/usr/bin/env python3
"""Curriculum training script for RL policy on CogsGuard.

Based on findings from issues #75 and #41:
- Phase 1: Arena (50x50), no_vibes, no_clips, 4 cogs, 1000-step episodes
- Phase 2: Competition map (88x88), no_vibes, 4 cogs, 3000-step episodes (key breakthrough)
- Key hyperparameters: entropy annealing, clip_coef, milestones_2 compounding factor

Usage:
  python scripts/train_curriculum_v2.py --phase 1 --epochs 80 --seed 42
  python scripts/train_curriculum_v2.py --phase 2 --epochs 30 --seed 42 --weights <path>
  python scripts/train_curriculum_v2.py --phase 2 --epochs 30 --seed 42 --weights <path> --m2-factor 25
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cogames.cli.mission import get_mission
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.train import train

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("curriculum_v2")


def patch_train_hyperparams(
    ent_coef: float = 0.01,
    clip_coef: float = 0.2,
    gamma: float = 0.995,
    gae_lambda: float = 0.90,
    learning_rate: float = 0.00092,
):
    """Monkey-patch PuffeRL init to override hardcoded hyperparameters."""
    import pufferlib.pufferl as pufferl_mod

    original_pufferl_init = pufferl_mod.PuffeRL.__init__

    def patched_pufferl_init(self, config, *pargs, **pkwargs):
        if isinstance(config, dict):
            config["ent_coef"] = ent_coef
            config["clip_coef"] = clip_coef
            config["gamma"] = gamma
            config["gae_lambda"] = gae_lambda
            config["learning_rate"] = learning_rate
            logger.info(f"Patched hyperparams: ent={ent_coef}, clip={clip_coef}, gamma={gamma}, gae={gae_lambda}, lr={learning_rate}")
        return original_pufferl_init(self, config, *pargs, **pkwargs)

    pufferl_mod.PuffeRL.__init__ = patched_pufferl_init


def make_env_config(phase: int, cogs: int, max_steps: int, m2_factor: float):
    if phase == 1:
        mission_name = "cogsguard_arena.basic"
        variant_list = ["no_vibes", "no_clips"]
    else:
        mission_name = "cogsguard_machina_1.basic"
        variant_list = ["no_vibes"]

    _, env_cfg, _ = get_mission(mission_name, variants_arg=variant_list, cogs=cogs)

    reward_variants = ["credit", f"milestones_2:{m2_factor}", "aligner"]
    apply_reward_variants(env_cfg, variants=reward_variants)

    env_cfg.game.max_steps = max_steps
    return env_cfg


def main():
    parser = argparse.ArgumentParser(description="Curriculum RL training for CogsGuard")
    parser.add_argument("--phase", type=int, choices=[1, 2], required=True)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--weights", type=str, default=None)
    parser.add_argument("--cogs", type=int, default=4)
    parser.add_argument("--parallel-envs", type=int, default=16)
    parser.add_argument("--checkpoint-dir", type=str, default=None)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--m2-factor", type=float, default=5.0)
    parser.add_argument("--ent-coef", type=float, default=0.04)
    parser.add_argument("--clip-coef", type=float, default=0.1)
    parser.add_argument("--lr", type=float, default=0.00092)
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--gae-lambda", type=float, default=0.90)
    parser.add_argument("--log-outputs", action="store_true")
    parser.add_argument("--checkpoint-interval", type=int, default=10)

    args = parser.parse_args()

    if args.max_steps is None:
        args.max_steps = 1000 if args.phase == 1 else 3000

    if args.checkpoint_dir is None:
        tag = f"p{args.phase}_m2x{int(args.m2_factor)}_s{args.seed}"
        args.checkpoint_dir = f"./train_dir_curriculum_{tag}"

    patch_train_hyperparams(
        ent_coef=args.ent_coef,
        clip_coef=args.clip_coef,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        learning_rate=args.lr,
    )

    env_cfg = make_env_config(args.phase, args.cogs, args.max_steps, args.m2_factor)

    logger.info(f"Phase {args.phase} training:")
    logger.info(f"  Map: {'arena 50x50' if args.phase == 1 else 'machina1 88x88'}")
    logger.info(f"  Cogs: {args.cogs}, MaxSteps: {args.max_steps}, Epochs: {args.epochs}")
    logger.info(f"  m2_factor: {args.m2_factor}, ent: {args.ent_coef}, clip: {args.clip_coef}")
    logger.info(f"  Weights: {args.weights}")
    logger.info(f"  Output: {args.checkpoint_dir}")

    steps_per_epoch = args.parallel_envs * args.max_steps * args.cogs
    total_steps = args.epochs * steps_per_epoch
    logger.info(f"  Steps/epoch: {steps_per_epoch:,}, Total: {total_steps:,}")

    device = torch.device("cpu")
    checkpoint_path = Path(args.checkpoint_dir)
    checkpoint_path.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    train(
        env_cfg=env_cfg,
        policy_class_path="cogames.policy.tutorial_policy.TutorialPolicy",
        device=device,
        initial_weights_path=args.weights,
        num_steps=total_steps,
        checkpoints_path=checkpoint_path,
        seed=args.seed,
        minibatch_size=4096,
        vector_num_envs=args.parallel_envs,
        log_outputs=args.log_outputs,
        checkpoint_interval=args.checkpoint_interval,
    )
    elapsed = time.time() - start_time
    logger.info(f"Training completed in {elapsed:.0f}s ({elapsed/60:.1f}m)")


if __name__ == "__main__":
    main()
