"""RL training script with fixed map seed and reward shaping.

Addresses the key findings from previous RL training sessions:
1. Fixed map seed across all envs (training metrics become meaningful)
2. Arena (50x50) for shorter navigation distances
3. NoVibes (5-action space) matching top RL policies
4. Credit + milestones_2 reward shaping for dense signals
5. Entropy annealing via env var overrides

Usage:
    source .venv/bin/activate
    python scripts/train_rl_fixed_map.py [--steps N] [--map arena|machina] [--hearts N] [--ent-coef F]
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
from cogames.train import train


def main():
    parser = argparse.ArgumentParser(description="RL training with fixed map and reward shaping")
    parser.add_argument("--steps", type=int, default=10_000_000, help="Total training steps")
    parser.add_argument("--map", choices=["arena", "machina"], default="arena", help="Map to train on")
    parser.add_argument("--hearts", type=int, default=255, help="Initial hearts (255=braveheart)")
    parser.add_argument("--cogs", type=int, default=8, help="Number of agents")
    parser.add_argument("--rewards", nargs="*", default=["credit", "milestones_2"], help="Reward variants")
    parser.add_argument("--ent-coef", type=float, default=None, help="Entropy coefficient override")
    parser.add_argument("--lr", type=float, default=None, help="Learning rate override")
    parser.add_argument("--seed", type=int, default=42, help="Training seed")
    parser.add_argument("--map-seed", type=int, default=None, help="Fixed map seed (default=same as seed)")
    parser.add_argument("--policy", default="class=tutorial", help="Policy class")
    parser.add_argument("--checkpoints", default="./train_dir_custom", help="Checkpoint directory")
    parser.add_argument("--no-vibes", action="store_true", default=True, help="Disable change_vibe (5-action)")
    parser.add_argument("--difficulty", default=None, help="Difficulty level")
    args = parser.parse_args()

    mission_name = "cogsguard_arena.basic" if args.map == "arena" else "cogsguard_machina_1.basic"

    variants = ["no_vibes"] if args.no_vibes else []
    if args.hearts >= 255:
        variants.append("braveheart")

    _, env_cfg, _ = get_mission(
        mission_name,
        variants_arg=variants if variants else None,
        cogs=args.cogs,
        difficulty=args.difficulty,
    )

    if args.rewards:
        apply_reward_variants(env_cfg, variants=args.rewards)
        print(f"Applied reward variants: {args.rewards}")

    if args.ent_coef is not None:
        os.environ["COGAMES_ENT_COEF"] = str(args.ent_coef)
    if args.lr is not None:
        os.environ["COGAMES_LR"] = str(args.lr)

    print(f"Training config:")
    print(f"  Mission: {mission_name}")
    print(f"  Variants: {variants}")
    print(f"  Reward variants: {args.rewards}")
    print(f"  Hearts: {args.hearts}")
    print(f"  Cogs: {args.cogs}")
    print(f"  Steps: {args.steps}")
    print(f"  Policy: {args.policy}")
    print(f"  Map seed: {args.map_seed or args.seed}")
    print(f"  Action space: {'5 (no vibes)' if args.no_vibes else '12 (with vibes)'}")
    print(f"  Num actions: {len(env_cfg.game.actions.move.__class__.__fields__)}")

    agent_rewards = env_cfg.game.agents[0].rewards if env_cfg.game.agents else {}
    print(f"  Configured rewards: {list(agent_rewards.keys())}")

    policy_spec_parts = args.policy.split(",")
    policy_class = "tutorial"
    policy_data = None
    for part in policy_spec_parts:
        if part.startswith("class="):
            policy_class = part.split("=", 1)[1]
        elif part.startswith("data="):
            policy_data = part.split("=", 1)[1]

    from mettagrid.policy.loader import resolve_policy_class_path
    class_path = resolve_policy_class_path(policy_class)

    device = torch.device("cpu")
    print(f"  Device: {device}")
    print(f"  Policy class: {class_path}")
    print()

    train(
        env_cfg=env_cfg,
        policy_class_path=class_path,
        initial_weights_path=policy_data,
        device=device,
        num_steps=args.steps,
        checkpoints_path=Path(args.checkpoints),
        seed=args.seed,
        map_seed=args.map_seed if args.map_seed is not None else args.seed,
        minibatch_size=4096,
        vector_num_envs=64,
        log_outputs=True,
        checkpoint_interval=10,
    )


if __name__ == "__main__":
    main()
