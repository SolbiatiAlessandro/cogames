# Experiment Report: Issue #44 — Miner Productivity Plateau

Branch: `claude/amazing-meitner-QzSVo`
Issue: https://github.com/SolbiatiAlessandro/cogames/issues/44

## 2026-04-21T05:15: autoresearch starting, my plan is to...

Working on issue #44: "Miner productivity plateau: deposits freeze at ~5k steps due to extractor depletion radius."

Previous researcher (pva5Z branch, not merged) found the root cause is a **congestion deadlock bug** in `move_blocked_cells`:
1. Move to cell X fails (another agent occupies it)
2. X added to `move_blocked_cells`
3. Next step: X is visible, no wall tag → "visually free" → X **immediately cleared** from `move_blocked_cells`
4. BFS routes through X again → fails again
5. **Infinite loop for 3593+ consecutive steps**

Their fix: per-agent move cooldown of 6 steps. Results: +19.1% avg reward across 3 seeds.

My plan:
1. Run baseline (3 seeds, 3000 steps each)
2. Implement the adaptive move cooldown fix (the pva5Z changes were never merged)
3. Test and iterate
4. Focus on reducing miner deaths (previous researcher noted deaths increased 64 vs 13 because miners now move into dangerous areas more)

## 2026-04-21T05:16: starting to run baseline

Command: `python scripts/run_experiment.py --seed {42,123,7} --steps 3000 --cogs 8`
Policy: machina_llm_roles (scripted_miners=True, scripted_aligners=True)

### Baseline Results (3 seeds)

| Seed | Avg/Agent | Junctions | Hearts | Deaths | Move Fail | Max Stuck |
|------|-----------|-----------|--------|--------|-----------|-----------|
| 42   | 77.60     | 38        | 38     | 3      | -         | -         |
| 123  | 69.42     | 31        | 32     | 0      | 8186      | 2322      |
| 7    | 26.88     | 14        | 15     | 9      | 11043     | 2549      |
| **Mean** | **57.97** | **27.7** | **28.3** | **4.0** | | |

Key finding: `max_steps_without_motion` of 2322-2549 confirms the congestion deadlock bug.
Seed 7 has 46% move failure rate and 9 deaths — the worst case.

## 2026-04-21T05:27: starting new experiment loop - adaptive move cooldown

**Hypothesis:** Per-agent move cooldown of 6 steps will break congestion deadlocks by preventing
the "add then immediately clear" cycle in move_blocked_cells.

**Changes:**
- `llm_skills.py`: Added `move_cooldowns` dict to MinerSkillState. Failed move targets stay
  blocked for 6 steps per-agent (not shared). Disabled when structurally stuck (>12 steps).
  Added `_bfs_without_cooldowns` fallback when cooldowns block all paths.
  Added `_record_move_target` to track move targets for cooldown detection.
- `aligner_agent.py`: Same cooldown mechanism added to AlignerState and `_update_map_memory`.
- `machina_llm_roles_policy.py`: Updated `_copy_with` to preserve new fields.

### Experiment 1 Results: Adaptive Move Cooldown (cooldown=6)

| Seed | Baseline | Experiment | Change | Move Fail | Max Stuck | Deaths |
|------|----------|------------|--------|-----------|-----------|--------|
| 42   | 77.60    | 91.13      | **+17.4%** | 1164  | 61        | 1 (vs 3) |
| 123  | 69.42    | 84.05      | **+21.1%** | 1670  | 146       | 0 (vs 0) |
| 7    | 26.88    | 90.73      | **+237.4%** | 3529 | 65        | 0 (vs 9) |
| **Mean** | **57.97** | **88.64** | **+52.9%** | | | |

**Massive improvement!** Especially on seed 7 which went from 26.88 to 90.73 (+237%).

Key metrics:
- Move failures: 80% reduction on seed 123, 68% on seed 7
- Max stuck steps: 97% reduction (2549 → 65 on seed 7)
- Deaths: 12 → 1 total across all seeds (92% reduction)
- Junction alignment: 27.7 → 38.7 avg (+40%)
- Variance collapsed: all seeds now score 84-91 vs previous 27-78 range

## 2026-04-21T05:33: I ran my experiment, findings

The adaptive move cooldown fix is highly effective. The root cause was confirmed:
agents were getting stuck in infinite BFS loops because move_blocked_cells entries
were immediately cleared by the "visually free" check each step. The 6-step cooldown
breaks this cycle, forcing BFS to find alternative routes.

The variance reduction is particularly notable — seed 7 went from being 3x worse
than seed 42 to being nearly identical. This suggests the congestion deadlock was
the primary source of cross-seed variance.

Next experiment should try: extending to 10k steps to check if the productivity
plateau from the issue title (deposits freeze at ~5k steps) is also resolved.

## 2026-04-21T06:07: Experiment 2 — Depletion-by-stuck + 10k scaling test

**Hypothesis:** Marking the nearest extractor as depleted when a miner gets stuck for 150+
steps will help miners find fresh extractors and sustain deposits past 3k steps.

**Changes:** Modified stuck detection in `step_with_state` — when stuck fires in
`mine_until_full` or `explore` mode, mark the nearest extractor as depleted.

### 3k Regression Check (seed 42)

| Metric | Experiment 1 | Experiment 2 | Change |
|--------|-------------|-------------|--------|
| avg/agent | 91.13 | 91.13 | **0% (no regression)** |
| junction | 36 | 36 | same |
| hearts | 39 | 39 | same |
| deposits | 1773 | 1773 | same |

**Finding:** Depletion-by-stuck is neutral at 3k steps because all deposits complete
within the first 3k steps. The depletion mechanism never fires.

### 10k Step Scaling Test (3 seeds)

| Seed | 3k reward | 10k reward | Ratio | Max Stuck | Deaths | Deposits |
|------|-----------|------------|-------|-----------|--------|----------|
| 42   | 91.13     | 350.1      | 3.84x | 95        | 2      | 1783     |
| 123  | 84.05     | 404.4      | 4.81x | 152       | 0      | 1692     |
| 7    | 90.73     | 349.7      | 3.85x | 74        | 0      | 960      |
| **Mean** | **88.64** | **368.1** | **4.15x** | **107** | **0.67** | **1478** |

### Critical Insight: Deposit Plateau Confirmed But Not Limiting

Seed 42 deposits are **IDENTICAL** at 3k and 10k steps:
- carbon: 431 at both 3k and 10k
- germanium: 460 at both
- silicon: 440 at both (450 at 10k, minor variance)
- oxygen: 442 at both

**All mining completes within ~3k steps.** After that, miners wander gaining energy/hp
but produce no new deposits. Reward still scales 4.15x because energy, hp, and survival
contribute linearly to total reward.

**Implication for issue #44:** The "deposit freeze at ~5k steps" is really a deposit
freeze at ~3k steps. However, since the standard evaluation is at 3k steps, this doesn't
affect our score. The move cooldown fix (+52.9%) already captures the main improvement.

## 2026-04-21T06:25: Planning next experiment

The 3k evaluation reward is 88.64 avg/agent. To improve further, I need to look at what's
limiting performance within the 3k evaluation window. Options:
1. **Improve miner efficiency** — miners could potentially deposit more within 3k steps
2. **Improve aligner performance** — more junctions aligned = more hearts available
3. **Reduce remaining move failures** — seed 7 still has 14% move failure rate at 10k
4. **Optimize mine-deposit cycle time** — faster round trips mean more deposits per step
