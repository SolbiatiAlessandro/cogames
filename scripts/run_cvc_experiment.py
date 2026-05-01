#!/usr/bin/env python3
"""Run a CvC experiment simulating online tournament conditions.

Our policy controls `our_cogs` agents, a partner policy controls the rest.
Usage:
    python scripts/run_cvc_experiment.py --seed 42 --our-cogs 2 --total-cogs 8 --our-aligners auto
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

log = logging.getLogger("run_cvc_experiment")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--total-cogs", type=int, default=8)
    parser.add_argument("--our-cogs", type=int, default=2)
    parser.add_argument("--our-aligners", type=str, default="auto")
    parser.add_argument("--partner", type=str, default="starter",
                        choices=["starter", "noop", "cross_role", "machina"])
    parser.add_argument("--our-positions", type=str, default="first",
                        choices=["first", "last", "spread"],
                        help="Where to place our agents: first (0..N-1), last (end), spread (every 4th)")
    parser.add_argument("--mission", type=str, default="basic")
    args = parser.parse_args()

    from cogames.cogs_vs_clips.missions import get_core_missions
    from mettagrid.policy.policy import PolicySpec
    from mettagrid.runner.rollout import run_episode_local

    missions = {m.name: m for m in get_core_missions()}
    mission = missions[args.mission]
    env_cfg = mission.make_env()

    if args.total_cogs != mission.num_agents:
        env_cfg = env_cfg.model_copy(
            update={"game": env_cfg.game.model_copy(update={"num_agents": args.total_cogs})}
        )
    if args.steps != mission.max_steps:
        env_cfg = env_cfg.model_copy(
            update={"game": env_cfg.game.model_copy(update={"max_steps": args.steps})}
        )

    our_kwargs = {"scripted_miners": True, "scripted_aligners": True}
    if args.our_aligners != "auto":
        our_kwargs["num_aligners"] = int(args.our_aligners)

    our_policy = PolicySpec(
        class_path="cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy",
        init_kwargs=our_kwargs,
    )

    partner_map = {
        "starter": "cogames.policy.starter_agent.StarterPolicy",
        "cross_role": "cogames.policy.cross_role_policy.CrossRolePolicy",
        "machina": "cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy",
    }
    partner_policy = PolicySpec(
        class_path=partner_map[args.partner],
        init_kwargs={"scripted_miners": True, "scripted_aligners": True} if args.partner == "machina" else {},
    )

    # Build assignment list based on position strategy
    if args.our_positions == "last":
        assignments = [1] * (args.total_cogs - args.our_cogs) + [0] * args.our_cogs
    elif args.our_positions == "spread":
        assignments = [1] * args.total_cogs
        step = max(args.total_cogs // args.our_cogs, 1)
        for i in range(args.our_cogs):
            assignments[i * step] = 0
    else:
        assignments = [0] * args.our_cogs + [1] * (args.total_cogs - args.our_cogs)

    log.info("CvC: our=%d partner=%d total=%d our_aligners=%s partner=%s seed=%d",
             args.our_cogs, args.total_cogs - args.our_cogs, args.total_cogs,
             args.our_aligners, args.partner, args.seed)

    start = time.time()
    results, _replay = run_episode_local(
        policy_specs=[our_policy, partner_policy],
        assignments=assignments,
        env=env_cfg,
        seed=args.seed,
        device="cpu",
        render_mode="none",
        autostart=True,
    )
    elapsed = time.time() - start

    total_reward = sum(results.rewards)
    num_agents = len(results.rewards)
    our_rewards = [results.rewards[i] for i in range(num_agents) if assignments[i] == 0]
    partner_rewards = [results.rewards[i] for i in range(num_agents) if assignments[i] == 1]

    agent_stats = results.stats.get("agent", [])
    totals: dict[str, float] = {}
    for agent in agent_stats:
        for key, value in agent.items():
            totals[key] = totals.get(key, 0) + value

    log.info("Episode finished in %.1fs", elapsed)
    log.info("RESULT steps=%d total_reward=%.6f avg_reward=%.6f", results.steps, total_reward, total_reward / num_agents)
    log.info("RESULT our_total=%.6f our_avg=%.6f", sum(our_rewards), sum(our_rewards) / len(our_rewards))
    log.info("RESULT partner_total=%.6f partner_avg=%.6f", sum(partner_rewards), sum(partner_rewards) / max(len(partner_rewards), 1))

    print(f"\n=== CVC EXPERIMENT RESULT ===")
    print(f"seed={args.seed} steps={results.steps}")
    print(f"total_reward={total_reward:.6f} avg_per_agent={total_reward / num_agents:.6f}")
    print(f"our_agents={args.our_cogs} our_total={sum(our_rewards):.6f} our_avg={sum(our_rewards) / len(our_rewards):.6f}")
    print(f"partner_agents={args.total_cogs - args.our_cogs} partner_total={sum(partner_rewards):.6f}")
    print(f"our_rewards={[f'{r:.4f}' for r in our_rewards]}")
    print(f"junction.held={totals.get('aligned.junction.held', 0):.0f}")
    print(f"heart.gained={totals.get('heart.gained', 0):.0f}")
    print(f"carbon.deposited={totals.get('cogs/carbon.deposited', 0):.0f}")
    print(f"oxygen.deposited={totals.get('cogs/oxygen.deposited', 0):.0f}")
    print(f"germanium.deposited={totals.get('cogs/germanium.deposited', 0):.0f}")
    print(f"silicon.deposited={totals.get('cogs/silicon.deposited', 0):.0f}")


if __name__ == "__main__":
    main()
