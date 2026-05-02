#!/usr/bin/env python3
"""Run a CvC experiment: N of our agents + (total-N) starter agents.

This simulates online tournament conditions where our policy controls
a subset of agents and the rest use the starter policy.

Usage:
    python scripts/run_cvc_experiment.py [--seed SEED] [--steps STEPS] [--our-agents N] [--total-agents T]
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("cvc_experiment_run.log", mode="w", encoding="utf-8"),
    ],
)
for _name in (
    "cogames.policy.llm_miner",
    "cogames.policy.machina_llm_roles",
    "cogames.policy.llm_skills",
    "cogames.policy.aligner_agent",
):
    logging.getLogger(_name).setLevel(logging.DEBUG)

log = logging.getLogger("run_cvc_experiment")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--our-agents", type=int, default=2)
    parser.add_argument("--total-agents", type=int, default=8)
    parser.add_argument("--mission", type=str, default="basic")
    args = parser.parse_args()

    from cogames.cogs_vs_clips.missions import get_core_missions
    from mettagrid.policy.policy import PolicySpec
    from mettagrid.runner.rollout import run_episode_local

    missions = {m.name: m for m in get_core_missions()}
    mission = missions[args.mission]
    env_cfg = mission.make_env()

    env_cfg = env_cfg.model_copy(
        update={"game": env_cfg.game.model_copy(update={
            "num_agents": args.total_agents,
            "max_steps": args.steps,
        })}
    )

    our_policy = PolicySpec(
        class_path="cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy",
        init_kwargs={"scripted_miners": True, "scripted_aligners": True},
    )
    starter_policy = PolicySpec(
        class_path="cogames.policy.starter_agent.StarterPolicy",
        init_kwargs={},
    )

    assignments = [0] * args.our_agents + [1] * (args.total_agents - args.our_agents)

    log.info("CvC: %d our agents + %d starter = %d total, steps=%d, seed=%d",
             args.our_agents, args.total_agents - args.our_agents, args.total_agents, args.steps, args.seed)

    start = time.time()
    results, _replay = run_episode_local(
        policy_specs=[our_policy, starter_policy],
        assignments=assignments,
        env=env_cfg,
        seed=args.seed,
        device="cpu",
        render_mode="none",
        autostart=True,
    )
    elapsed = time.time() - start

    our_rewards = [results.rewards[i] for i in range(args.our_agents)]
    starter_rewards = [results.rewards[i] for i in range(args.our_agents, args.total_agents)]
    our_avg = sum(our_rewards) / len(our_rewards) if our_rewards else 0
    starter_avg = sum(starter_rewards) / len(starter_rewards) if starter_rewards else 0

    agent_stats = results.stats.get("agent", [])
    totals: dict[str, float] = {}
    for agent in agent_stats:
        for key, value in agent.items():
            totals[key] = totals.get(key, 0) + value

    log.info("Episode finished in %.1fs", elapsed)
    log.info("RESULT our_avg=%.6f starter_avg=%.6f", our_avg, starter_avg)
    log.info("RESULT our_rewards=%s", [f"{r:.4f}" for r in our_rewards])

    print(f"\n=== CvC EXPERIMENT RESULT ===")
    print(f"seed={args.seed} steps={results.steps} our_agents={args.our_agents} total={args.total_agents}")
    print(f"our_avg_reward={our_avg:.6f}")
    print(f"starter_avg_reward={starter_avg:.6f}")
    print(f"our_rewards={[f'{r:.2f}' for r in our_rewards]}")
    print(f"junction.held={totals.get('aligned.junction.held', 0):.0f}")
    print(f"heart.gained={totals.get('heart.gained', 0):.0f}")
    print(f"elapsed={elapsed:.1f}s")


if __name__ == "__main__":
    main()
