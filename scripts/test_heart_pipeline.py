#!/usr/bin/env python3
"""Quick 8-agent test to diagnose heart pipeline and agent mortality."""
from __future__ import annotations

import logging
import os
import sys

os.environ.setdefault("OPENROUTER_API_KEY", "dummy")

LOG_FILE = "heart_pipeline_test.log"
_fmt = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=_fmt,
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
    ],
)
for _name in (
    "cogames.policy.cross_role",
    "cogames.policy.machina_llm_roles",
    "cogames.policy.aligner_agent",
):
    logging.getLogger(_name).setLevel(logging.DEBUG)

log = logging.getLogger("test_heart_pipeline")

MAX_STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 2000

from cogames.cogs_vs_clips.missions import make_cogsguard_mission
from cogames.play import run_episode_local
from mettagrid.policy.policy import PolicySpec

mission = make_cogsguard_mission(num_agents=8, max_steps=MAX_STEPS)
env_cfg = mission.make_env()

policy_spec = PolicySpec(
    class_path="cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy",
    init_kwargs={},
)

log.info("Running 8-agent %d-step test...", MAX_STEPS)

results, _replay = run_episode_local(
    policy_specs=[policy_spec],
    assignments=[0] * 8,
    env=env_cfg,
    replay_path=None,
    seed=int(sys.argv[2]) if len(sys.argv) > 2 else 42,
    device="cpu",
    render_mode="none",
)

log.info("=" * 70)
log.info("Steps: %d", results.steps)

# Print all stats
for key in sorted(results.stats.keys()):
    val = results.stats[key]
    if val != 0:
        log.info("  %s = %s", key, val)

# Print per-agent stats
mr = getattr(results, 'mission_reward', None)
if mr is not None:
    log.info("Mission reward: %.6f", mr)
else:
    game = results.stats.get("game", {}) if isinstance(results.stats.get("game"), dict) else {}
    jxn = game.get("cogs/aligned.junction.gained", 0)
    log.info("Junctions gained: %s (mission_reward attr not available)", jxn)

# Extract key metrics
game = results.stats.get("game", {}) if isinstance(results.stats.get("game"), dict) else {}
agent_list = results.stats.get("agent", [])
if isinstance(agent_list, list):
    log.info("--- Per-agent summary ---")
    for i, a in enumerate(agent_list):
        if isinstance(a, dict):
            log.info("  agent[%d]: hp=%s hearts_gained=%s hearts_lost=%s junctions=%s deaths=%s gear=%s",
                i, a.get('hp.amount', '?'), a.get('heart.gained', 0), a.get('heart.lost', 0),
                a.get('junction.aligned_by_agent', 0), a.get('death', 0),
                'miner' if a.get('miner.gained', 0) > 0 and a.get('aligner.gained', 0) == 0 else 'aligner' if a.get('aligner.gained', 0) > 0 else 'unknown')
