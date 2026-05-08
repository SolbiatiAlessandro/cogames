# Experiment Log: claude/amazing-meitner-EnIvJ (Issue #64)

## Goal
Gear contamination prevention — agents lose gear by stepping on wrong-type stations during navigation. Fix this to reduce variance and improve median scores.

## Prior Work (NNt07 branch, not merged)
- BFS-level hazard avoidance: regressed or no effect
- Fast recovery (detect gear loss mid-skill -> gear_up): +1.1% avg
- Approach rotation on contamination: +0.75% avg, +4.1% on worst seed
- Agent 7 on seed 123 still stuck: never gets miner gear, so contamination rotation never triggers
- Key learning: aggressive BFS changes alter exploration too much; contamination-triggered fixes are safe

## My Plan
1. Re-implement the proven fast-recovery + approach-rotation from NNt07
2. Fix optimistic BFS to also avoid hazard stations (currently only _bfs_first_direction does)
3. Add timeout-based miner station skip (for agents that never get gear)
4. Validate with 5 seeds

---

2026-05-08T00:00: autoresearch starting, my plan is to implement gear contamination prevention for issue #64. Prior researcher found fast-recovery + approach-rotation gave +0.75% avg. I'll re-implement those, plus fix hazard avoidance gaps in optimistic BFS and add timeout-based station skip.

2026-05-08T00:01: starting to run baseline (5 seeds: 42, 123, 7, 99, 555)

2026-05-08T00:15: baseline result is:

| Seed | Reward | Deposits | Hearts | Junctions |
|------|--------|----------|--------|-----------|
| 42 | 3.183 | 2162 | 22 | 28836 |
| 123 | 1.810 | 1536 | 27 | 15104 |
| 7 | 2.530 | 1500 | 18 | 22303 |
| 99 | 3.015 | 1511 | 19 | 27152 |
| 555 | 3.707 | 2608 | 32 | 34071 |
| **Avg** | **2.849** | **1863** | **24** | **25493** |

Seed 123 is worst performer — contamination-prone layout.

2026-05-08T00:20: starting new experiment loop. In this experiment I want to try three things:
1. Hazard avoidance in _bfs_optimistic_direction (was missing)
2. Fast gear recovery: detect gear loss mid-skill -> immediate gear_up switch
3. Approach rotation on contamination: when gear is lost during mining/depositing, rotate approach side for next gear_up

My hypothesis is that these combined will reduce gear churn especially on seed 123.

2026-05-08T00:45: I ran experiment 1 (all three fixes combined). Results:

| Seed | Baseline | Exp1 | Delta |
|------|----------|------|-------|
| 42 | 3.183 | 3.424 | **+7.5%** |
| 123 | 1.810 | 2.165 | **+19.6%** |
| 7 | 2.530 | 2.590 | +2.4% |
| 99 | 3.015 | 3.015 | 0.0% |
| 555 | 3.707 | 3.708 | 0.0% |
| **Avg** | **2.849** | **2.980** | **+4.6%** |

This is a strong result. Seed 123 improved dramatically (+19.6%). Seeds without contamination are unchanged or slightly improved. No regressions. Key insight: miner.gained on seed 123 went from 1.2 to 2.2 — the fast recovery is working, agents are re-equipping faster after contamination.

Next experiment should try: explore with hazard avoidance (stepping into unknown cells near hazard stations), or further refining the approach rotation
