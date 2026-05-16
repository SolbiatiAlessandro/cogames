"""RL training with curriculum on junction distance.

Phase 1: Train with junctions very close (max_distance=6) — within 13x13 obs window
Phase 2: Increase to max_distance=10
Phase 3: Full distance (max_distance=15) — competition setting

This addresses the navigation bottleneck: agents learn junction alignment first
on easy maps, then learn to navigate further as distance increases.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import torch
from cogames.cli.mission import get_mission
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips import terrain
from cogames.train import train


def patch_junction_distance(max_distance: int):
    """Monkey-patch both MachinaArena and SequentialMachinaArena to use a different max_distance."""
    for cls_name in ("MachinaArena", "SequentialMachinaArena"):
        cls = getattr(terrain, cls_name, None)
        if cls is None:
            continue
        original = cls.get_children

        def make_patched(orig):
            def patched_get_children(self):
                children = orig(self)
                for child in children:
                    if isinstance(child.scene, terrain.EnsureHubReachableJunctionConfig):
                        child.scene.max_distance = max_distance
                return children
            return patched_get_children

        cls.get_children = make_patched(original)
        print(f"  [CURRICULUM] Patched {cls_name}.get_children max_distance to {max_distance}")


def main():
    parser = argparse.ArgumentParser(description="Curriculum RL training")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2, 3], help="Curriculum phase")
    parser.add_argument("--steps", type=int, default=2000000, help="Steps per phase")
    parser.add_argument("--cogs", type=int, default=4, help="Number of agents")
    parser.add_argument("--ent-coef", type=float, default=0.02, help="Entropy coefficient")
    parser.add_argument("--weights", default=None, help="Initial weights (for continuation)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reward", default="credit,milestones_2", help="Reward variants (comma-separated)")
    parser.add_argument("--mission", default="cogsguard_arena.basic", help="Mission to train on")
    parser.add_argument("--max-steps", type=int, default=None, help="Override episode max_steps")
    parser.add_argument("--tag", default="", help="Extra tag for output dir name")
    parser.add_argument("--num-envs", type=int, default=64, help="Number of parallel envs")
    parser.add_argument("--checkpoint-interval", type=int, default=10, help="Checkpoint every N epochs")
    args = parser.parse_args()

    phase_config = {
        1: {"max_distance": 6, "desc": "Close junctions (within obs window)"},
        2: {"max_distance": 10, "desc": "Medium distance junctions"},
        3: {"max_distance": 15, "desc": "Full distance (competition)"},
    }

    phase = phase_config[args.phase]
    print(f"=== CURRICULUM PHASE {args.phase}: {phase['desc']} ===")
    print(f"  max_distance: {phase['max_distance']}")
    print(f"  steps: {args.steps}")
    print(f"  mission: {args.mission}")
    print(f"  reward variants: {args.reward}")
    print(f"  initial weights: {args.weights or 'random'}")

    patch_junction_distance(phase["max_distance"])

    _, env_cfg, _ = get_mission(
        args.mission,
        variants_arg=["no_vibes", "braveheart"],
        cogs=args.cogs,
    )

    if args.max_steps is not None:
        env_cfg.game.max_steps = args.max_steps
        print(f"  Override max_steps to {args.max_steps}")

    reward_variants = [v.strip() for v in args.reward.split(",") if v.strip()]
    apply_reward_variants(env_cfg, variants=reward_variants)

    if args.ent_coef:
        os.environ["COGAMES_ENT_COEF"] = str(args.ent_coef)

    from mettagrid.policy.loader import resolve_policy_class_path
    class_path = resolve_policy_class_path("tutorial")

    tag = f"_{args.tag}" if args.tag else ""
    checkpoint_dir = Path(f"./train_dir_curriculum_p{args.phase}{tag}")

    train(
        env_cfg=env_cfg,
        policy_class_path=class_path,
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


if __name__ == "__main__":
    main()
