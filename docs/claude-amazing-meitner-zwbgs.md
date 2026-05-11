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

## Next experiments to try
- Combine aligner CD=3 with miner CD=3 (gave +2.9% but seed 123 regressed — might work better online)
- Try stopping move_blocked_cells additions after 12+ stuck steps (agent is deeply stuck, permanent blocks are counterproductive)
- Aligner hub approach rotation on repeated hub failures
- Online validation via upload
