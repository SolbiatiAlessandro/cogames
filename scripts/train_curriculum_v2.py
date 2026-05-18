#!/usr/bin/env python3
"""Curriculum training script for RL policy on CogsGuard.

Entropy annealing is done via successive training runs with decreasing ent_coef,
since PufferLib uses a fixed ent_coef per run.

Usage (full pipeline):
  python scripts/train_curriculum_v2.py --pipeline arena_anneal --seed 42 --m2-factor 5
  python scripts/train_curriculum_v2.py --pipeline compmap --seed 42 --weights <p1_best> --m2-factor 25

Usage (single phase):
  python scripts/train_curriculum_v2.py --phase 1 --epochs 30 --seed 42 --ent-coef 0.02
"""
from __future__ import annotations

import argparse
import glob
import logging
import os
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


def find_best_checkpoint(checkpoint_dir: str) -> str | None:
    """Find the latest checkpoint in a directory."""
    pattern = os.path.join(checkpoint_dir, "*/model_*.pt")
    checkpoints = sorted(glob.glob(pattern), key=os.path.getmtime)
    return checkpoints[-1] if checkpoints else None


def find_checkpoint_at_epoch(checkpoint_dir: str, epoch: int) -> str | None:
    """Find checkpoint at specific epoch."""
    pattern = os.path.join(checkpoint_dir, f"*/model_{epoch:06d}.pt")
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def run_training_phase(
    phase: int,
    steps_total: int,
    seed: int,
    cogs: int,
    parallel_envs: int,
    max_steps: int,
    m2_factor: float,
    ent_coef: float,
    clip_coef: float,
    lr: float,
    gamma: float,
    gae_lambda: float,
    weights: str | None,
    checkpoint_dir: str,
    checkpoint_interval: int = 5,
    log_outputs: bool = True,
    map_seed: int | None = None,
):
    patch_train_hyperparams(
        ent_coef=ent_coef,
        clip_coef=clip_coef,
        gamma=gamma,
        gae_lambda=gae_lambda,
        learning_rate=lr,
    )

    env_cfg = make_env_config(phase, cogs, max_steps, m2_factor)

    logger.info(f"Phase {phase} training (ent={ent_coef}, clip={clip_coef}):")
    logger.info(f"  Map: {'arena 50x50' if phase == 1 else 'machina1 88x88'}")
    logger.info(f"  Cogs: {cogs}, MaxSteps: {max_steps}")
    logger.info(f"  m2_factor: {m2_factor}, lr: {lr}")
    logger.info(f"  map_seed: {map_seed}, optimizer_seed: {seed}")
    logger.info(f"  Weights: {weights}")
    logger.info(f"  Output: {checkpoint_dir}")
    logger.info(f"  Total steps: {steps_total:,}")

    device = torch.device("cpu")
    checkpoint_path = Path(checkpoint_dir)
    checkpoint_path.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    train(
        env_cfg=env_cfg,
        policy_class_path="cogames.policy.tutorial_policy.TutorialPolicy",
        device=device,
        initial_weights_path=weights,
        num_steps=steps_total,
        checkpoints_path=checkpoint_path,
        seed=seed,
        map_seed=map_seed,
        minibatch_size=4096,
        vector_num_envs=parallel_envs,
        log_outputs=log_outputs,
        checkpoint_interval=checkpoint_interval,
    )
    elapsed = time.time() - start_time
    logger.info(f"Training phase completed in {elapsed:.0f}s ({elapsed/60:.1f}m)")

    best = find_best_checkpoint(checkpoint_dir)
    logger.info(f"Best checkpoint: {best}")
    return best


def pipeline_arena_anneal(args):
    """Phase 1 with entropy annealing: 0.08→0.02→0.01 on arena."""
    base_dir = f"./train_dir_p1_anneal_m2x{int(args.m2_factor)}_s{args.seed}"
    steps_per_batch = args.parallel_envs * 1000 * args.cogs  # per pufferl batch

    # Stage 1a: High entropy exploration (ent=0.08, 20 pufferl-epochs worth)
    logger.info("=" * 60)
    logger.info("STAGE 1a: High entropy exploration (ent=0.08)")
    logger.info("=" * 60)
    stage1a_dir = f"{base_dir}/stage1a"
    stage1a_steps = 30 * steps_per_batch  # ~30 pufferl epochs
    map_seed = getattr(args, 'map_seed', None)
    weights_1a = run_training_phase(
        phase=1, steps_total=stage1a_steps, seed=args.seed,
        cogs=args.cogs, parallel_envs=args.parallel_envs, max_steps=1000,
        m2_factor=args.m2_factor, ent_coef=0.08, clip_coef=0.1,
        lr=0.00092, gamma=0.995, gae_lambda=0.90,
        weights=args.weights, checkpoint_dir=stage1a_dir,
        map_seed=map_seed,
    )

    # Stage 1b: Medium entropy (ent=0.02, 40 epochs from 1a)
    logger.info("=" * 60)
    logger.info("STAGE 1b: Medium entropy (ent=0.02)")
    logger.info("=" * 60)
    stage1b_dir = f"{base_dir}/stage1b"
    stage1b_steps = 50 * steps_per_batch
    weights_1b = run_training_phase(
        phase=1, steps_total=stage1b_steps, seed=args.seed,
        cogs=args.cogs, parallel_envs=args.parallel_envs, max_steps=1000,
        m2_factor=args.m2_factor, ent_coef=0.02, clip_coef=0.1,
        lr=0.00092, gamma=0.995, gae_lambda=0.90,
        weights=weights_1a, checkpoint_dir=stage1b_dir,
        map_seed=map_seed,
    )

    # Stage 1c: Low entropy exploitation (ent=0.01, 30 epochs from 1b)
    logger.info("=" * 60)
    logger.info("STAGE 1c: Low entropy exploitation (ent=0.01)")
    logger.info("=" * 60)
    stage1c_dir = f"{base_dir}/stage1c"
    stage1c_steps = 30 * steps_per_batch
    weights_1c = run_training_phase(
        phase=1, steps_total=stage1c_steps, seed=args.seed,
        cogs=args.cogs, parallel_envs=args.parallel_envs, max_steps=1000,
        m2_factor=args.m2_factor, ent_coef=0.01, clip_coef=0.1,
        lr=0.00092, gamma=0.995, gae_lambda=0.90,
        weights=weights_1b, checkpoint_dir=stage1c_dir,
        map_seed=map_seed,
    )

    logger.info("=" * 60)
    logger.info(f"ARENA ANNEALING COMPLETE. Best checkpoint: {weights_1c}")
    logger.info("=" * 60)
    return weights_1c


def pipeline_compmap(args):
    """Phase 2 on competition map with 3000-step episodes (the key breakthrough)."""
    map_seed = getattr(args, 'map_seed', None)
    ms_label = f"_ms{map_seed}" if map_seed is not None else ""
    base_dir = f"./train_dir_p2_longep_m2x{int(args.m2_factor)}_s{args.seed}{ms_label}"
    steps_per_batch = args.parallel_envs * 3000 * args.cogs

    if not args.weights:
        logger.error("Phase 2 requires --weights (Phase 1 checkpoint)")
        sys.exit(1)

    # Phase 2: Competition map, 3000-step episodes, clip=0.2 (withclips finding)
    logger.info("=" * 60)
    logger.info("PHASE 2: Competition map, 3000-step episodes")
    logger.info(f"  map_seed={map_seed} (Session 6: map_seed=42 gives favorable layout)")
    logger.info("=" * 60)
    p2_steps = 30 * steps_per_batch
    weights_p2 = run_training_phase(
        phase=2, steps_total=p2_steps, seed=args.seed,
        cogs=args.cogs, parallel_envs=args.parallel_envs, max_steps=3000,
        m2_factor=args.m2_factor, ent_coef=0.01, clip_coef=0.2,
        lr=0.00092, gamma=0.995, gae_lambda=0.90,
        weights=args.weights, checkpoint_dir=base_dir,
        map_seed=map_seed,
    )

    logger.info("=" * 60)
    logger.info(f"PHASE 2 COMPLETE. Best checkpoint: {weights_p2}")
    logger.info("=" * 60)
    return weights_p2


def pipeline_compmap_graduated(args):
    """Phase 2 with intermediate 1000-step step (matching Session 2's successful pipeline)."""
    map_seed = getattr(args, 'map_seed', None)
    ms_label = f"_ms{map_seed}" if map_seed is not None else ""

    if not args.weights:
        logger.error("Graduated pipeline requires --weights (Phase 1 checkpoint)")
        sys.exit(1)

    # Phase 2a: Competition map, 1000-step episodes (learn map navigation)
    p2a_dir = f"./train_dir_p2a_1kep_m2x{int(args.m2_factor)}_s{args.seed}{ms_label}"
    steps_per_batch_1k = args.parallel_envs * 1000 * args.cogs
    p2a_steps = 20 * steps_per_batch_1k

    logger.info("=" * 60)
    logger.info("PHASE 2a: Competition map, 1000-step episodes (map navigation)")
    logger.info(f"  map_seed={map_seed}")
    logger.info("=" * 60)
    weights_p2a = run_training_phase(
        phase=2, steps_total=p2a_steps, seed=args.seed,
        cogs=args.cogs, parallel_envs=args.parallel_envs, max_steps=1000,
        m2_factor=args.m2_factor, ent_coef=0.02, clip_coef=0.2,
        lr=0.00092, gamma=0.995, gae_lambda=0.90,
        weights=args.weights, checkpoint_dir=p2a_dir,
        map_seed=map_seed,
    )

    # Phase 2b: Competition map, 3000-step episodes (extend horizon)
    p2b_dir = f"./train_dir_p2b_3kep_m2x{int(args.m2_factor)}_s{args.seed}{ms_label}"
    steps_per_batch_3k = args.parallel_envs * 3000 * args.cogs
    p2b_steps = 30 * steps_per_batch_3k

    logger.info("=" * 60)
    logger.info("PHASE 2b: Competition map, 3000-step episodes (horizon extension)")
    logger.info(f"  From: {weights_p2a}")
    logger.info("=" * 60)
    weights_p2b = run_training_phase(
        phase=2, steps_total=p2b_steps, seed=args.seed,
        cogs=args.cogs, parallel_envs=args.parallel_envs, max_steps=3000,
        m2_factor=args.m2_factor, ent_coef=0.01, clip_coef=0.2,
        lr=0.00092, gamma=0.995, gae_lambda=0.90,
        weights=weights_p2a, checkpoint_dir=p2b_dir,
        map_seed=map_seed,
    )

    logger.info("=" * 60)
    logger.info(f"GRADUATED PIPELINE COMPLETE. Best checkpoint: {weights_p2b}")
    logger.info("=" * 60)
    return weights_p2b


def main():
    parser = argparse.ArgumentParser(description="Curriculum RL training for CogsGuard")

    # Pipeline mode
    parser.add_argument("--pipeline", type=str, choices=["arena_anneal", "compmap", "compmap_graduated"],
                        help="Run full pipeline")

    # Single phase mode
    parser.add_argument("--phase", type=int, choices=[1, 2])
    parser.add_argument("--epochs", type=int, default=30)

    # Common args
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--map-seed", type=int, default=None,
                        help="Fixed map seed (Session 6: map_seed=42 gives favorable layout)")
    parser.add_argument("--weights", type=str, default=None)
    parser.add_argument("--cogs", type=int, default=4)
    parser.add_argument("--parallel-envs", type=int, default=16)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--m2-factor", type=float, default=5.0)
    parser.add_argument("--ent-coef", type=float, default=0.02)
    parser.add_argument("--clip-coef", type=float, default=0.1)
    parser.add_argument("--lr", type=float, default=0.00092)
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--gae-lambda", type=float, default=0.90)
    parser.add_argument("--log-outputs", action="store_true", default=True)
    parser.add_argument("--checkpoint-dir", type=str, default=None)

    args = parser.parse_args()

    if args.pipeline == "arena_anneal":
        pipeline_arena_anneal(args)
    elif args.pipeline == "compmap":
        pipeline_compmap(args)
    elif args.pipeline == "compmap_graduated":
        pipeline_compmap_graduated(args)
    elif args.phase:
        if args.max_steps is None:
            args.max_steps = 1000 if args.phase == 1 else 3000
        if args.checkpoint_dir is None:
            args.checkpoint_dir = f"./train_dir_p{args.phase}_ent{args.ent_coef}_m2x{int(args.m2_factor)}_s{args.seed}"

        steps_per_batch = args.parallel_envs * args.max_steps * args.cogs
        total_steps = args.epochs * steps_per_batch

        run_training_phase(
            phase=args.phase, steps_total=total_steps, seed=args.seed,
            cogs=args.cogs, parallel_envs=args.parallel_envs, max_steps=args.max_steps,
            m2_factor=args.m2_factor, ent_coef=args.ent_coef, clip_coef=args.clip_coef,
            lr=args.lr, gamma=args.gamma, gae_lambda=args.gae_lambda,
            weights=args.weights, checkpoint_dir=args.checkpoint_dir,
            map_seed=args.map_seed,
        )
    else:
        parser.error("Specify either --pipeline or --phase")


if __name__ == "__main__":
    main()
