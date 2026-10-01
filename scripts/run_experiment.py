#!/usr/bin/env python3
"""Run a CoGames experiment and print results in machine-readable format."""
from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
for _name in ("cogames.policy.machina_llm_roles", "cogames.policy.aligner_agent"):
    logging.getLogger(_name).setLevel(logging.INFO)

from cogames.cogs_vs_clips.missions import get_core_missions
from mettagrid.policy.policy import PolicySpec
from mettagrid.runner.rollout import run_episode_local


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--num-aligners", type=int, default=3)
    parser.add_argument("--num-scouts", type=int, default=0)
    parser.add_argument("--stuck-threshold", type=int, default=28)
    parser.add_argument("--llm-timeout", type=float, default=0.001)
    parser.add_argument("--return-load", type=int, default=40)
    args = parser.parse_args()

    missions = {m.name: m for m in get_core_missions()}
    m = missions["basic"]
    env_cfg = m.make_env()
    if args.steps != env_cfg.game.max_steps:
        env_cfg = env_cfg.model_copy(
            update={"game": env_cfg.game.model_copy(update={"max_steps": args.steps})}
        )

    policy_spec = PolicySpec(
        class_path="cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy",
        init_kwargs={
            "num_aligners": args.num_aligners,
            "num_scouts": args.num_scouts,
            "scripted_miners": True,
            "stuck_threshold": args.stuck_threshold,
            "llm_timeout_s": args.llm_timeout,
            "return_load": args.return_load,
        },
    )

    results, _ = run_episode_local(
        policy_specs=[policy_spec],
        assignments=[0] * env_cfg.game.num_agents,
        env=env_cfg,
        seed=args.seed,
        device="cpu",
        render_mode="none",
    )

    total_reward = sum(results.rewards)
    num_agents = len(results.rewards)
    avg_reward = total_reward / num_agents if num_agents else 0.0

    stats = results.stats
    agent_stats = stats.get("agent", [])
    totals: dict[str, float] = {}
    for agent in agent_stats:
        for key, value in agent.items():
            totals[key] = totals.get(key, 0) + value

    out = {
        "seed": args.seed,
        "steps": results.steps,
        "total_reward": round(total_reward, 6),
        "avg_reward": round(avg_reward, 6),
        "num_agents": num_agents,
        "junction_aligned": int(totals.get("junction.aligned_by_agent", totals.get("aligned.junction.gained", 0))),
        "hearts_gained": int(totals.get("heart.gained", 0)),
        "hearts_lost": int(totals.get("heart.lost", 0)),
        "deaths": int(totals.get("death", 0)),
        "aligner_gained": int(totals.get("aligner.gained", 0)),
        "aligner_lost": int(totals.get("aligner.lost", 0)),
        "scout_gained": int(totals.get("scout.gained", 0)),
        "scrambler_gained": int(totals.get("scrambler.gained", 0)),
        "miner_gained": int(totals.get("miner.gained", 0)),
        "action_failed": int(totals.get("action.failed", 0)),
        "max_stuck": int(totals.get("status.max_steps_without_motion", 0)),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
