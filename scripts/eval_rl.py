"""Evaluate an RL checkpoint using run_episode_local (correct API).

Usage:
    source .venv/bin/activate
    python scripts/eval_rl.py --checkpoint ./train_dir_*/model_000060.pt --steps 500 --episodes 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main():
    parser = argparse.ArgumentParser(description="Evaluate RL checkpoint")
    parser.add_argument("--checkpoint", required=True, help="Path to model checkpoint")
    parser.add_argument("--mission", default="cogsguard_machina_1.basic")
    parser.add_argument("--cogs", type=int, default=8)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--temp", type=float, default=0.7, help="Sampling temperature")
    parser.add_argument("--max-distance", type=int, default=None, help="Patch junction max_distance (match training)")
    parser.add_argument("--start-aligner", action="store_true", help="Start agents with aligner gear")
    parser.add_argument("--start-heart", action="store_true", help="Start agents with heart")
    parser.add_argument("--flat-map", action="store_true", help="Flat terrain (no biomes)")
    args = parser.parse_args()

    from cogames.cli.mission import get_mission
    from mettagrid.policy.policy import PolicySpec
    from mettagrid.runner.rollout import run_episode_local

    if args.max_distance is not None:
        from cogames.cogs_vs_clips import terrain
        for cls_name in ("MachinaArena", "SequentialMachinaArena"):
            cls = getattr(terrain, cls_name, None)
            if cls is None:
                continue
            original = cls.get_children
            max_d = args.max_distance
            def make_patched(orig, md=max_d):
                def patched(self):
                    children = orig(self)
                    for child in children:
                        if isinstance(child.scene, terrain.EnsureHubReachableJunctionConfig):
                            child.scene.max_distance = md
                    return children
                return patched
            cls.get_children = make_patched(original)
        print(f"[EVAL] Patched junction max_distance to {args.max_distance}")

    _, env_cfg, _ = get_mission(
        args.mission,
        variants_arg=["no_vibes", "braveheart"],
        cogs=args.cogs,
    )
    env_cfg.game.max_steps = args.steps

    if args.start_aligner or args.start_heart:
        agent_cfgs = env_cfg.game.agents if env_cfg.game.agents else [env_cfg.game.agent]
        for agent_cfg in agent_cfgs:
            if args.start_aligner:
                agent_cfg.inventory.initial["aligner"] = 1
            if args.start_heart:
                agent_cfg.inventory.initial["heart"] = 1
        if args.start_aligner:
            print("[EVAL] Agents start with aligner gear")
        if args.start_heart:
            print("[EVAL] Agents start with heart")

    if args.flat_map:
        from mettagrid.mapgen.mapgen import MapGen
        mb = env_cfg.game.map_builder
        if isinstance(mb, MapGen.Config) and hasattr(mb.instance, 'hub'):
            mb.instance.biome_weights = {"none": 1.0}
            mb.instance.dungeon_weights = {"none": 1.0}
            mb.instance.base_biome_config = {"cluster_prob": 0.0}
            mb.instance.asteroid_mask = None
            print("[EVAL] Flat map (no biomes/dungeons)")

    policy_class = "cogames.policy.tutorial_policy.TutorialPolicy"
    checkpoint = str(Path(args.checkpoint).resolve())

    results_list = []
    for ep in range(args.episodes):
        seed = args.seed + ep
        policy_spec = PolicySpec(
            class_path=policy_class,
            data_path=checkpoint,
        )
        result, _ = run_episode_local(
            policy_specs=[policy_spec],
            assignments=[0] * args.cogs,
            env=env_cfg,
            seed=seed,
            device="cpu",
            render_mode="none",
            autostart=True,
        )
        total_r = sum(result.rewards)
        avg_r = total_r / len(result.rewards) if result.rewards else 0
        results_list.append(avg_r)

        agent_stats = result.stats.get("agent", [])
        totals = {}
        for agent in agent_stats:
            for key, value in agent.items():
                totals[key] = totals.get(key, 0) + value

        jh = totals.get("aligned.junction.held", 0)
        jg = totals.get("aligned.junction.gained", 0)
        ja = totals.get("junction.aligned_by_agent", 0)
        hg = totals.get("heart.gained", 0)
        ag = totals.get("aligner.gained", 0)
        print(f"Episode {ep} (seed={seed}): avg_reward={avg_r:.4f} steps={result.steps} junc_aligned={ja:.0f} junction.held={jh:.0f} heart.gained={hg:.0f} aligner.gained={ag:.0f}")

    avg_all = sum(results_list) / len(results_list)
    peak = max(results_list)
    print(f"\n=== SUMMARY ({args.episodes} episodes, {args.steps} steps) ===")
    print(f"Average per-agent reward: {avg_all:.4f}")
    print(f"Peak per-agent reward: {peak:.4f}")
    print(f"All rewards: {[f'{r:.4f}' for r in results_list]}")


if __name__ == "__main__":
    main()
