#!/usr/bin/env python3
"""Navigation diagnostics: measure move success rate, BFS cascade usage,
and stuck time for aligner agents.

Usage:
    python scripts/nav_diagnostic.py [--seed SEED] [--steps STEPS]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s | %(message)s")

_counters: dict = {}

def _reset_counters():
    global _counters
    _counters = {
        "move_attempts": defaultdict(int),
        "move_successes": defaultdict(int),
        "total_steps": defaultdict(int),
        "stuck_steps": defaultdict(int),
        "bfs_primary_ok": defaultdict(int),
        "bfs_cooldown_ok": defaultdict(int),
        "bfs_optimistic_ok": defaultdict(int),
        "greedy_used": defaultdict(int),
        "nav_with_target": defaultdict(int),
        "nav_no_target": defaultdict(int),
        "mode_steps": defaultdict(lambda: defaultdict(int)),
        "move_blocked_sizes": defaultdict(list),
        "cooldown_sizes": defaultdict(list),
        "known_free_sizes": defaultdict(list),
        "skill_steps": defaultdict(lambda: defaultdict(int)),
    }


def _patch():
    import cogames.policy.aligner_agent as aa
    import cogames.policy.machina_llm_roles_policy as mlrp

    orig_step = mlrp.LLMAlignerPolicyImpl._step_impl
    orig_update = aa.AlignerPolicyImpl._update_map_memory
    orig_align = aa.AlignerPolicyImpl._align_neutral
    orig_move_toward = aa.AlignerPolicyImpl._move_toward_target
    orig_gear_up = aa.AlignerPolicyImpl._gear_up
    orig_get_heart = aa.AlignerPolicyImpl._get_heart

    def patched_step(self, obs, state):
        c = _counters
        aid = obs.agent_id
        c["total_steps"][aid] += 1

        if state.steps_since_last_move > 3:
            c["stuck_steps"][aid] += 1

        c["move_blocked_sizes"][aid].append(len(state.move_blocked_cells))
        c["cooldown_sizes"][aid].append(len(state.move_cooldowns))
        c["known_free_sizes"][aid].append(len(state.known_free_cells))

        action, new_state = orig_step(self, obs, state)

        action_name = action.name if hasattr(action, "name") else ""
        if action_name.startswith("move_"):
            c["move_attempts"][aid] += 1

        mode = new_state.last_mode if hasattr(new_state, "last_mode") else "unknown"
        c["mode_steps"][aid][mode] = c["mode_steps"][aid].get(mode, 0) + 1

        skill = new_state.current_skill if hasattr(new_state, "current_skill") else "unknown"
        if skill:
            c["skill_steps"][aid][skill] = c["skill_steps"][aid].get(skill, 0) + 1

        return action, new_state

    def patched_update(self, obs, state):
        aid = obs.agent_id
        old_pos = state.last_pos
        result = orig_update(self, obs, state)
        if old_pos is not None and result != old_pos:
            _counters["move_successes"][aid] += 1
        return result

    def patched_align(self, obs, state, current_abs):
        aid = obs.agent_id
        c = _counters
        bl = state.blacklisted_junctions
        alignable = {j for j in (state.known_neutral_junctions | state.known_enemy_junctions)
                     if self._is_alignable(j, state) and j not in bl}
        target = self._cascade_priority_target(current_abs, alignable, state)
        if target is not None:
            c["nav_with_target"][aid] += 1
            d1 = self._bfs_first_direction(state, current_abs, target, avoid_hazards=True)
            if d1 is None:
                d1 = self._bfs_first_direction(state, current_abs, target, avoid_hazards=False)
            if d1 is not None:
                c["bfs_primary_ok"][aid] += 1
            else:
                d2 = self._bfs_without_cooldowns(state, current_abs, target, avoid_hazards=True)
                if d2 is not None:
                    c["bfs_cooldown_ok"][aid] += 1
                else:
                    d3 = self._bfs_optimistic_direction(state, current_abs, target, avoid_hazards=True)
                    if d3 is None:
                        d3 = self._bfs_optimistic_direction(state, current_abs, target, avoid_hazards=False)
                    if d3 is not None:
                        c["bfs_optimistic_ok"][aid] += 1
                    else:
                        c["greedy_used"][aid] += 1
        else:
            c["nav_no_target"][aid] += 1

        return orig_align(self, obs, state, current_abs)

    mlrp.LLMAlignerPolicyImpl._step_impl = patched_step
    aa.AlignerPolicyImpl._update_map_memory = patched_update
    aa.AlignerPolicyImpl._align_neutral = patched_align

    return {
        "step": (mlrp.LLMAlignerPolicyImpl, "_step_impl", orig_step),
        "update": (aa.AlignerPolicyImpl, "_update_map_memory", orig_update),
        "align": (aa.AlignerPolicyImpl, "_align_neutral", orig_align),
    }


def _unpatch(originals):
    for key, (cls, attr, orig) in originals.items():
        setattr(cls, attr, orig)


def run_diagnostic(seed: int, steps: int = 3000, num_cogs: int = 8, num_aligners: int = 4):
    from cogames.cogs_vs_clips.missions import get_core_missions
    from mettagrid.policy.policy import PolicySpec
    from mettagrid.runner.rollout import run_episode_local

    _reset_counters()
    originals = _patch()

    missions = {m.name: m for m in get_core_missions()}
    mission = missions["basic"]
    env_cfg = mission.make_env()

    if num_cogs != mission.num_agents:
        env_cfg = env_cfg.model_copy(
            update={"game": env_cfg.game.model_copy(update={"num_agents": num_cogs})}
        )
    if steps != mission.max_steps:
        env_cfg = env_cfg.model_copy(
            update={"game": env_cfg.game.model_copy(update={"max_steps": steps})}
        )

    policy_spec = PolicySpec(
        class_path="cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy",
        init_kwargs={"scripted_miners": True, "scripted_aligners": True},
    )

    try:
        results, _ = run_episode_local(
            policy_specs=[policy_spec],
            assignments=[0] * env_cfg.game.num_agents,
            env=env_cfg,
            seed=seed,
            device="cpu",
            render_mode="none",
            autostart=True,
        )
    finally:
        _unpatch(originals)

    total_reward = sum(results.rewards)
    num_agents = len(results.rewards)
    avg_reward = total_reward / num_agents if num_agents else 0

    agent_stats = results.stats.get("agent", [])
    totals: dict[str, float] = {}
    for agent in agent_stats:
        for key, value in agent.items():
            totals[key] = totals.get(key, 0) + value

    c = _counters
    # Identify aligner agent IDs (they have total_steps)
    aligner_ids = sorted(c["total_steps"].keys())

    print(f"\n{'='*80}")
    print(f"NAV DIAGNOSTICS — seed={seed}, steps={steps}")
    print(f"  reward(total)={total_reward:.2f}, junction.held={totals.get('aligned.junction.held', 0):.0f}")
    print(f"  junction.gained={totals.get('aligned.junction.gained', 0):.0f}, heart.gained={totals.get('heart.gained', 0):.0f}")
    print(f"{'='*80}")

    # Movement efficiency
    print(f"\n--- Movement Efficiency (all agents) ---")
    print(f"{'Agent':>6} {'Role':>7} {'Total':>6} {'MvAtt':>6} {'MvSuc':>6} {'Fail%':>6} {'Stuck':>6} {'Stk%':>5}")
    for aid in aligner_ids:
        t = c["total_steps"][aid]
        ma = c["move_attempts"][aid]
        ms = c["move_successes"][aid]
        fail_pct = ((ma - ms) / ma * 100) if ma > 0 else 0
        ss = c["stuck_steps"][aid]
        stuck_pct = (ss / t * 100) if t > 0 else 0
        role = "ALIGN" if any(c["skill_steps"][aid].get(s, 0) > 0 for s in ("align_neutral", "get_heart")) else "MINER"
        print(f"{aid:>6} {role:>7} {t:>6} {ma:>6} {ms:>6} {fail_pct:>5.1f}% {ss:>6} {stuck_pct:>4.1f}%")

    total_ma = sum(c["move_attempts"].values())
    total_ms = sum(c["move_successes"].values())
    total_ss = sum(c["stuck_steps"].values())
    total_t = sum(c["total_steps"].values())
    agg_fail = ((total_ma - total_ms) / total_ma * 100) if total_ma > 0 else 0
    agg_stuck = (total_ss / total_t * 100) if total_t > 0 else 0
    print(f"{'ALL':>6} {'':>7} {total_t:>6} {total_ma:>6} {total_ms:>6} {agg_fail:>5.1f}% {total_ss:>6} {agg_stuck:>4.1f}%")

    # BFS cascade
    align_ids = [aid for aid in aligner_ids if c["nav_with_target"][aid] + c["nav_no_target"][aid] > 0]
    if align_ids:
        print(f"\n--- BFS Cascade (align_neutral calls with a target) ---")
        print(f"{'Agent':>6} {'w/Tgt':>6} {'BFS-1':>6} {'BFS-cd':>6} {'BFS-op':>6} {'Greed':>6} {'noTgt':>6}")
        for aid in align_ids:
            wt = c["nav_with_target"][aid]
            b1 = c["bfs_primary_ok"][aid]
            bc = c["bfs_cooldown_ok"][aid]
            bo = c["bfs_optimistic_ok"][aid]
            g = c["greedy_used"][aid]
            nt = c["nav_no_target"][aid]
            print(f"{aid:>6} {wt:>6} {b1:>6} {bc:>6} {bo:>6} {g:>6} {nt:>6}")

    # Skill distribution (aligners only)
    print(f"\n--- Skill Distribution (aligners) ---")
    all_skills = set()
    for aid in aligner_ids:
        all_skills.update(c["skill_steps"][aid].keys())
    skills = sorted(all_skills)
    if skills:
        header = f"{'Agent':>6} " + " ".join(f"{s[:11]:>11}" for s in skills)
        print(header)
        for aid in aligner_ids:
            if any(c["skill_steps"][aid].get(s, 0) > 0 for s in ("align_neutral", "get_heart")):
                vals = " ".join(f"{c['skill_steps'][aid].get(s, 0):>11}" for s in skills)
                print(f"{aid:>6} {vals}")

    # Mode distribution
    print(f"\n--- Mode Distribution (aligners) ---")
    all_modes = set()
    for aid in aligner_ids:
        all_modes.update(c["mode_steps"][aid].keys())
    modes = sorted(all_modes)
    if modes:
        header = f"{'Agent':>6} " + " ".join(f"{m[:12]:>12}" for m in modes)
        print(header)
        for aid in aligner_ids:
            if any(c["skill_steps"][aid].get(s, 0) > 0 for s in ("align_neutral", "get_heart")):
                vals = " ".join(f"{c['mode_steps'][aid].get(m, 0):>12}" for m in modes)
                print(f"{aid:>6} {vals}")

    # Blocked cells
    print(f"\n--- Blocked Cells (aligners) ---")
    print(f"{'Agent':>6} {'MvBlk-end':>10} {'MvBlk-max':>10} {'CD-max':>7} {'Free-end':>9}")
    for aid in aligner_ids:
        if any(c["skill_steps"][aid].get(s, 0) > 0 for s in ("align_neutral", "get_heart")):
            mb = c["move_blocked_sizes"][aid]
            cd = c["cooldown_sizes"][aid]
            kf = c["known_free_sizes"][aid]
            mb_end = mb[-1] if mb else 0
            mb_max = max(mb) if mb else 0
            cd_max = max(cd) if cd else 0
            kf_end = kf[-1] if kf else 0
            print(f"{aid:>6} {mb_end:>10} {mb_max:>10} {cd_max:>7} {kf_end:>9}")

    return avg_reward


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--steps", type=int, default=3000)
    args = parser.parse_args()

    for seed in args.seed:
        run_diagnostic(seed, args.steps)


if __name__ == "__main__":
    main()
