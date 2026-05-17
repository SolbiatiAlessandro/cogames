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


def patch_junction_distance(max_distance: int, min_distance: int = None):
    """Monkey-patch both MachinaArena and SequentialMachinaArena to use a different max_distance."""
    for cls_name in ("MachinaArena", "SequentialMachinaArena"):
        cls = getattr(terrain, cls_name, None)
        if cls is None:
            continue
        original = cls.get_children

        def make_patched(orig, max_d=max_distance, min_d=min_distance):
            def patched_get_children(self):
                children = orig(self)
                for child in children:
                    if isinstance(child.scene, terrain.EnsureHubReachableJunctionConfig):
                        child.scene.max_distance = max_d
                        if min_d is not None:
                            child.scene.min_distance = min_d
                return children
            return patched_get_children

        cls.get_children = make_patched(original)
        print(f"  [CURRICULUM] Patched {cls_name}.get_children max_distance to {max_distance}, min_distance to {min_distance}")


def main():
    parser = argparse.ArgumentParser(description="Curriculum RL training")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2, 3], help="Curriculum phase")
    parser.add_argument("--max-distance", type=int, default=None, help="Override curriculum max_distance")
    parser.add_argument("--min-distance", type=int, default=None, help="Override curriculum min_distance")
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
    parser.add_argument("--explore-weight", type=float, default=0.0, help="cell.visited reward weight")
    parser.add_argument("--ent-start", type=float, default=0.0, help="Entropy annealing start (0=disabled)")
    parser.add_argument("--ent-end", type=float, default=0.0, help="Entropy annealing end")
    parser.add_argument("--ent-anneal-frac", type=float, default=0.3, help="Fraction of training for annealing")
    parser.add_argument("--obs-size", type=int, default=13, help="Observation window size (max 15)")
    parser.add_argument("--goal-obs", action="store_true", help="Enable goal_obs for directional reward info")
    parser.add_argument("--boost-aligner", type=float, default=0.0,
                        help="Extra aligner_gained reward weight (no penalty for other gear)")
    parser.add_argument("--boost-heart", type=float, default=0.0,
                        help="Extra heart.gained/withdrawn reward weight")
    parser.add_argument("--no-hub-wall", action="store_true", help="Remove hub inner wall for easier exit")
    parser.add_argument("--randomize-spawns", action="store_true", help="Randomize agent spawn positions in hub")
    parser.add_argument("--flat-map", action="store_true", help="Disable biomes/dungeons for flat navigation")
    parser.add_argument("--start-aligner", action="store_true", help="Start agents with aligner gear")
    parser.add_argument("--start-heart", action="store_true", help="Start agents with heart")
    parser.add_argument("--no-explore", action="store_true", help="Disable cell.visited reward entirely")
    parser.add_argument("--no-clips", action="store_true", help="Remove clips ships from map")
    parser.add_argument("--clip-coef", type=float, default=0.2, help="PPO clip coefficient")
    parser.add_argument("--lr", type=float, default=0.00092, help="Learning rate")
    args = parser.parse_args()

    phase_config = {
        1: {"max_distance": 6, "desc": "Close junctions (within obs window)"},
        2: {"max_distance": 10, "desc": "Medium distance junctions"},
        3: {"max_distance": 15, "desc": "Full distance (competition)"},
    }

    phase = phase_config[args.phase]
    max_dist = args.max_distance if args.max_distance is not None else phase["max_distance"]
    print(f"=== CURRICULUM PHASE {args.phase}: {phase['desc']} ===")
    print(f"  max_distance: {max_dist}")
    print(f"  steps: {args.steps}")
    print(f"  mission: {args.mission}")
    print(f"  reward variants: {args.reward}")
    print(f"  initial weights: {args.weights or 'random'}")

    patch_junction_distance(max_dist, args.min_distance)

    _, env_cfg, _ = get_mission(
        args.mission,
        variants_arg=["no_vibes", "braveheart"],
        cogs=args.cogs,
    )

    from mettagrid.mapgen.mapgen import MapGen
    mb = env_cfg.game.map_builder
    if isinstance(mb, MapGen.Config) and mb.instance is not None:
        if args.no_clips and hasattr(mb.instance, 'map_corner_placements'):
            mb.instance.map_corner_placements = []
            print(f"  Removed clips ships from map")
    if isinstance(mb, MapGen.Config) and hasattr(mb.instance, 'hub'):
        if args.no_hub_wall:
            mb.instance.hub.include_inner_wall = False
            print(f"  Removed hub inner wall")
        if args.randomize_spawns:
            mb.instance.hub.randomize_spawn_positions = True
            print(f"  Randomized spawn positions")
        if args.flat_map:
            mb.instance.biome_weights = {"none": 1.0}
            mb.instance.dungeon_weights = {"none": 1.0}
            mb.instance.base_biome_config = {"cluster_prob": 0.0}
            mb.instance.asteroid_mask = None
            print(f"  Flat map (no biomes/dungeons/obstacles/asteroid)")

    if args.start_aligner or args.start_heart:
        agent_cfgs = env_cfg.game.agents if env_cfg.game.agents else [env_cfg.game.agent]
        for agent_cfg in agent_cfgs:
            if args.start_aligner:
                agent_cfg.inventory.initial["aligner"] = 1
            if args.start_heart:
                agent_cfg.inventory.initial["heart"] = 1
        if args.start_aligner:
            print(f"  Agents start with aligner gear")
        if args.start_heart:
            print(f"  Agents start with heart")

    if args.obs_size != 13:
        env_cfg.game.obs.width = args.obs_size
        env_cfg.game.obs.height = args.obs_size
        print(f"  Override obs size to {args.obs_size}x{args.obs_size}")

    if args.goal_obs:
        env_cfg.game.obs.global_obs.goal_obs = True
        print(f"  Enabled goal_obs")

    if args.max_steps is not None:
        env_cfg.game.max_steps = args.max_steps
        print(f"  Override max_steps to {args.max_steps}")

    reward_variants = [v.strip() for v in args.reward.split(",") if v.strip()]
    apply_reward_variants(env_cfg, variants=reward_variants)

    if args.boost_aligner > 0:
        from mettagrid.config.game_value import stat as game_stat
        from mettagrid.config.reward_config import reward as make_reward
        agent_cfgs = env_cfg.game.agents if env_cfg.game.agents else [env_cfg.game.agent]
        for agent_cfg in agent_cfgs:
            agent_cfg.rewards["aligner_gained"] = make_reward(
                game_stat("aligner.gained"), weight=args.boost_aligner
            )
            agent_cfg.rewards["junction_aligned_by_agent"] = make_reward(
                game_stat("junction.aligned_by_agent"), weight=args.boost_aligner * 2.5
            )
        print(f"  Boosted aligner_gained to {args.boost_aligner}, junction_aligned to {args.boost_aligner * 2.5}")

    if args.boost_heart > 0:
        from mettagrid.config.game_value import stat as game_stat
        from mettagrid.config.reward_config import reward as make_reward
        agent_cfgs = env_cfg.game.agents if env_cfg.game.agents else [env_cfg.game.agent]
        for agent_cfg in agent_cfgs:
            agent_cfg.rewards["heart_gained"] = make_reward(
                game_stat("heart.gained"), weight=args.boost_heart
            )
        print(f"  Boosted heart_gained to {args.boost_heart}")

    if args.explore_weight > 0:
        from mettagrid.config.game_value import stat as game_stat
        from mettagrid.config.reward_config import reward as make_reward
        agent_cfgs = env_cfg.game.agents if env_cfg.game.agents else [env_cfg.game.agent]
        for agent_cfg in agent_cfgs:
            agent_cfg.rewards["cell_visited_explore"] = make_reward(
                game_stat("cell.visited"), weight=args.explore_weight
            )
        print(f"  Added cell.visited exploration reward: weight={args.explore_weight}")

    if args.ent_start > 0 and args.ent_end > 0:
        os.environ["COGAMES_ENT_START"] = str(args.ent_start)
        os.environ["COGAMES_ENT_END"] = str(args.ent_end)
        os.environ["COGAMES_ENT_ANNEAL_FRAC"] = str(args.ent_anneal_frac)
        os.environ["COGAMES_ENT_COEF"] = str(args.ent_start)
        print(f"  Entropy annealing: {args.ent_start} → {args.ent_end} over {args.ent_anneal_frac*100}% of training")
    elif args.ent_coef:
        os.environ["COGAMES_ENT_COEF"] = str(args.ent_coef)

    if args.clip_coef != 0.2:
        os.environ["COGAMES_CLIP_COEF"] = str(args.clip_coef)
        print(f"  PPO clip_coef: {args.clip_coef}")

    if args.lr != 0.00092:
        os.environ["COGAMES_LR"] = str(args.lr)
        print(f"  Learning rate: {args.lr}")

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
