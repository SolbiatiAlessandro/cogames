# Experiment Log: claude/amazing-meitner-zwbgs

## Issue: #69 - Move failure rate reduction — 33% of aligner steps wasted bumping walls

2026-05-11 00:00: autoresearch starting, my plan is to:
1. Run baseline on current code (main + opt-v1 config)
2. Measure move failure rate as primary metric
3. Focus on the suggested experiments from issue #69

Key context from previous researcher (branch claude/amazing-meitner-Qh03p):
- Wall-following escape gave +2.4% reward (not merged to main)
- FIFO eviction on move_blocked_cells (cap=40) was neutral
- BFS move_blocked relaxation was neutral
- move_blocked_cells "pollution" serves as useful congestion heuristic — can't just remove it

## Baseline (3-seed avg at 3000 steps, 8 agents)

| Seed | Reward  | max_steps_without_motion |
|------|---------|--------------------------|
| 42   | 1026.80 | 126                      |
| 123  | 1076.31 | 155                      |
| 7    | 1117.62 | 147                      |
| **Avg** | **1073.58** |                    |

## Experiments tried (discarded)

### Wall-following escape (Experiment D)
- Implemented right-hand-rule wall-following for aligner and miner
- Key finding: the original navigation shake was DEAD CODE — `no_move_steps` never increments because `last_action_move` feature doesn't exist in observations
- Fixed to use `steps_since_last_move` (actual position tracking)
- When unguarded: -14% regression (agents leave their targets)
- With guard (skip near hub/junction/station): +1.3% seed 42, neutral avg
- Two-phase (shake 5-9 steps, wall-follow 10+): +1.3% seed 42, -1.6% seed 7, neutral avg
- **Status: DISCARD** — guard blocks almost all activations, inconsistent

### BFS without move_blocked relaxation
- Added `_bfs_without_move_blocked` fallback to BFS chain
- **Status: DISCARD** — -4.7% avg regression. Confirms issue finding: removing move_blocked_cells hurts.

### FIFO eviction on move_blocked_cells (cap=30)
- **Status: DISCARD** — zero effect. Visual clearing already handles stale entries.

### Move cooldown tuning
- CD=12 (longer avoidance): neutral (+0.1% avg)
- CD=2 (very short): -2.2% avg regression
- Aligner CD=3, Miner CD=4: +0.3% avg
- Both CD=3: +2.9% avg but high variance

## Experiment 1: Aligner cooldown reduction (CD=6 → CD=3)

**Hypothesis:** Shorter cooldowns let BFS retry blocked cells sooner, finding paths faster.

**Results:**

| Seed | Baseline | CD=3   | Change  |
|------|----------|--------|---------|
| 42   | 1026.80  | 1028.70| **+0.2%** |
| 123  | 1076.31  | 1104.19| **+2.6%** |
| 7    | 1117.62  | 1158.69| **+3.7%** |
| **Avg** | **1073.58** | **1097.19** | **+2.2%** |

**Status: KEEP** — consistent improvement across all seeds.

## Experiments tried on top of CD=3 (all discarded)

### Stuck threshold reduction (ST=12, ST=15)
- ST=12: avg 1087.21 (+1.3% vs baseline, -0.9% vs CD=3) — seed 123 regresses -3.0%
- ST=15: avg 1040.04 (-3.1% vs baseline) — regresses all seeds
- **Status: DISCARD** — cutting skill timeouts hurts at 3000 steps (prior +9% was at 500 steps only)

### Miner CD=3 (matching aligner)
- avg 1104.99 (+2.9% vs baseline, +0.7% vs CD=3) — but seed 123 -2.6%, max_stuck increased (190, 172, 153)
- **Status: DISCARD** — miners thrash more with shorter cooldowns, inconsistent

### Navigation shake fix (steps_since_last_move replaces dead no_move_steps)
- Guarded (skip near target): avg 1102.94 (+0.5% vs CD=3) — barely activates
- Unguarded: avg 1060.10 (-3.4% vs CD=3) — agents leave targets
- **Status: DISCARD** — agents are stuck near targets, not in transit; shake can't help

### Hub approach rotation on stuck
- Rotate preferred_side every 5 stuck steps: avg 1025.38 (-6.5% vs CD=3)
- **Status: DISCARD** — rotating disrupts approach progress

### BFS agent position avoidance
- Full BFS avoid: avg 1076.30 (-1.9% vs CD=3), max_stuck=275
- Approach cell only: avg 1083.18 (-1.3% vs CD=3)
- **Status: DISCARD** — too restrictive near hub clusters

### move_blocked_cells periodic clear (every 100 steps)
- avg 1097.19 (+0.0% vs CD=3) — identical results
- **Status: NEUTRAL** — visual clearing already handles stale entries

### Shared move cooldowns across agents
- avg 1093.58 (-0.3% vs CD=3), max_stuck=319
- **Status: DISCARD** — over-blocking cascading effect

## Summary

Only aligner CD=3 is a consistent improvement for issue #69 (+2.2% avg across 3 seeds).
Many complementary approaches tested but none improve further. The move failure problem
has diminishing returns — the congestion heuristic (move_blocked_cells) works well,
and reducing cooldown TTL (CD=3) is the sweet spot for BFS retry speed.

## Next experiments to try
- Online validation via upload
- Move to next priority issue
