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
    """Monkey-patch MachinaArena.get_children to use a different max_distance."""
    original_get_children = terrain.MachinaArena.get_children

    def patched_get_children(self):
        children = original_get_children(self)
        for child in children:
            if isinstance(child.scene, terrain.EnsureHubReachableJunctionConfig):
                child.scene.max_distance = max_distance
        return children

    terrain.MachinaArena.get_children = patched_get_children
    print(f"  [CURRICULUM] Patched junction max_distance to {max_distance}")


def main():
    parser = argparse.ArgumentParser(description="Curriculum RL training")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2, 3], help="Curriculum phase")
    parser.add_argument("--steps", type=int, default=2000000, help="Steps per phase")
    parser.add_argument("--cogs", type=int, default=4, help="Number of agents")
    parser.add_argument("--ent-coef", type=float, default=0.02, help="Entropy coefficient")
    parser.add_argument("--weights", default=None, help="Initial weights (for continuation)")
    parser.add_argument("--seed", type=int, default=42)
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
    print(f"  initial weights: {args.weights or 'random'}")

    patch_junction_distance(phase["max_distance"])

    _, env_cfg, _ = get_mission(
        "cogsguard_arena.basic",
        variants_arg=["no_vibes", "braveheart"],
        cogs=args.cogs,
    )

    apply_reward_variants(env_cfg, variants=["credit", "milestones_2"])

    if args.ent_coef:
        os.environ["COGAMES_ENT_COEF"] = str(args.ent_coef)

    from mettagrid.policy.loader import resolve_policy_class_path
    class_path = resolve_policy_class_path("tutorial")

    checkpoint_dir = Path(f"./train_dir_curriculum_p{args.phase}")

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
        vector_num_envs=64,
        log_outputs=True,
        checkpoint_interval=10,
    )


if __name__ == "__main__":
    main()
