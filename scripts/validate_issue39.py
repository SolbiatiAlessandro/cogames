#!/usr/bin/env python3
"""Validate merged MGrvP policy for issue #39 submission.

Runs 8-agent episodes at 1000 steps across seeds 42-44.
"""
from __future__ import annotations

import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("validate_issue39")

os.environ.setdefault("OPENROUTER_API_KEY", "")

from cogames.cogs_vs_clips.missions import get_core_missions
from cogames.play import _print_episode_stats
from mettagrid.policy.policy import PolicySpec
from mettagrid.runner.rollout import run_episode_local
from rich.console import Console

console = Console()

SEEDS = [int(s) for s in sys.argv[1:]] if len(sys.argv) > 1 else [42, 43, 44]
MAX_STEPS = int(os.environ.get("VALIDATE_MAX_STEPS", "1000"))

_all = get_core_missions()
mission = next(m for m in _all if m.name == "basic" and m.site.name == "cogsguard_machina_1")
env_cfg = mission.make_env()
env_cfg = env_cfg.model_copy(
    update={"game": env_cfg.game.model_copy(update={"max_steps": MAX_STEPS})}
)
n_agents = env_cfg.game.num_agents

policy_spec = PolicySpec(
    class_path="cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy",
    init_kwargs={},
)

log.info("Mission: basic, agents=%d, max_steps=%d, seeds=%s", n_agents, MAX_STEPS, SEEDS)

results_list = []
for seed in SEEDS:
    log.info("=== Running seed %d ===", seed)
    t0 = time.time()
    results, _replay = run_episode_local(
        policy_specs=[policy_spec],
        assignments=[0] * n_agents,
        env=env_cfg,
        seed=seed,
        device="cpu",
        render_mode="none",
    )
    elapsed = time.time() - t0

    total_reward = sum(results.rewards)
    avg_reward = total_reward / n_agents if n_agents else 0
    steps = results.steps

    agent_stats = results.stats.get("agent", [])
    totals = {}
    for agent in agent_stats:
        for key, value in agent.items():
            totals[key] = totals.get(key, 0) + value

    junctions = int(totals.get("aligned.junction.held", 0))
    hearts = int(totals.get("heart.gained", 0))
    hp = int(totals.get("hp.amount", 0))
    hp_max = n_agents * 100

    log.info(
        "Seed %d: total_reward=%.3f avg/agent=%.4f steps=%d junctions=%d hearts=%d hp=%d/%d (%.1fs)",
        seed, total_reward, avg_reward, steps, junctions, hearts, hp, hp_max, elapsed,
    )
    _print_episode_stats(console, results)

    results_list.append({
        "seed": seed,
        "total_reward": total_reward,
        "avg_reward": avg_reward,
        "steps": steps,
        "junctions": junctions,
        "hearts": hearts,
        "hp": hp,
        "elapsed": elapsed,
    })

log.info("=" * 60)
avg_total = sum(r["total_reward"] for r in results_list) / len(results_list)
avg_junctions = sum(r["junctions"] for r in results_list) / len(results_list)
avg_hearts = sum(r["hearts"] for r in results_list) / len(results_list)
log.info(
    "SUMMARY: %d seeds, %d steps, avg_total_reward=%.3f, avg_junctions=%.1f, avg_hearts=%.1f",
    len(results_list), MAX_STEPS, avg_total, avg_junctions, avg_hearts,
)
for r in results_list:
    log.info("  seed=%d total=%.3f junctions=%d hearts=%d hp=%d (%.1fs)",
             r["seed"], r["total_reward"], r["junctions"], r["hearts"], r["hp"], r["elapsed"])
