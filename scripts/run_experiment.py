#!/usr/bin/env python3
"""Run a cogames experiment and extract reward metrics.

Usage:
    python scripts/run_experiment.py [--seed SEED] [--steps STEPS] [--cogs N]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("experiment_run.log", mode="w", encoding="utf-8"),
    ],
)
for _name in (
    "cogames.policy.llm_miner",
    "cogames.policy.machina_llm_roles",
    "cogames.policy.llm_skills",
    "cogames.policy.aligner_agent",
):
    logging.getLogger(_name).setLevel(logging.DEBUG)

log = logging.getLogger("run_experiment")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--cogs", type=int, default=8)
    parser.add_argument("--mission", type=str, default="basic")
    parser.add_argument("--num-aligners", type=int, default=None)
    parser.add_argument("--return-load", type=int, default=None)
    parser.add_argument("--aligner-ids", type=str, default=None)
    args = parser.parse_args()

    from cogames.cogs_vs_clips.missions import get_core_missions
    from cogames.play import play
    from mettagrid.policy.policy import PolicySpec
    from rich.console import Console

    missions = {m.name: m for m in get_core_missions()}
    mission = missions[args.mission]
    env_cfg = mission.make_env()

    if args.cogs != mission.num_agents:
        env_cfg = env_cfg.model_copy(
            update={"game": env_cfg.game.model_copy(update={"num_agents": args.cogs})}
        )
    if args.steps != mission.max_steps:
        env_cfg = env_cfg.model_copy(
            update={"game": env_cfg.game.model_copy(update={"max_steps": args.steps})}
        )

    policy_kwargs = {
            "scripted_miners": True,
            "scripted_aligners": True,
    }
    if args.num_aligners is not None:
        policy_kwargs["num_aligners"] = args.num_aligners
    if args.return_load is not None:
        policy_kwargs["return_load"] = args.return_load
    if args.aligner_ids is not None:
        policy_kwargs["aligner_ids"] = args.aligner_ids

    policy_spec = PolicySpec(
        class_path="cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy",
        init_kwargs=policy_kwargs,
    )

    log.info("Mission=%s cogs=%d steps=%d seed=%d", args.mission, args.cogs, args.steps, args.seed)

    from mettagrid.runner.rollout import run_episode_local

    console = Console()
    start = time.time()
    results, _replay = run_episode_local(
        policy_specs=[policy_spec],
        assignments=[0] * env_cfg.game.num_agents,
        env=env_cfg,
        seed=args.seed,
        device="cpu",
        render_mode="none",
        autostart=True,
    )
    elapsed = time.time() - start

    total_reward = sum(results.rewards)
    num_agents = len(results.rewards)
    avg_reward = total_reward / num_agents if num_agents else 0

    agent_stats = results.stats.get("agent", [])
    totals: dict[str, float] = {}
    for agent in agent_stats:
        for key, value in agent.items():
            totals[key] = totals.get(key, 0) + value

    log.info("Episode finished in %.1fs", elapsed)
    log.info("RESULT steps=%d total_reward=%.6f avg_reward_per_agent=%.6f", results.steps, total_reward, avg_reward)
    log.info("RESULT rewards_per_agent=%s", [f"{r:.4f}" for r in results.rewards])

    for k in sorted(totals.keys()):
        if totals[k] != 0:
            log.info("STAT %s = %.1f", k, totals[k])

    print(f"\n=== EXPERIMENT RESULT ===")
    print(f"seed={args.seed} steps={results.steps} total_reward={total_reward:.6f} avg_per_agent={avg_reward:.6f}")
    print(f"junction.held={totals.get('aligned.junction.held', 0):.0f}")
    print(f"junction.gained={totals.get('aligned.junction.gained', 0):.0f}")
    print(f"heart.gained={totals.get('heart.gained', 0):.0f}")
    print(f"heart.withdrawn={totals.get('heart.withdrawn', 0):.0f}")
    print(f"carbon.deposited={totals.get('cogs/carbon.deposited', 0):.0f}")
    print(f"oxygen.deposited={totals.get('cogs/oxygen.deposited', 0):.0f}")
    print(f"germanium.deposited={totals.get('cogs/germanium.deposited', 0):.0f}")
    print(f"silicon.deposited={totals.get('cogs/silicon.deposited', 0):.0f}")


if __name__ == "__main__":
    main()
