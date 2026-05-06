# Director Notes
_Written: 2026-05-06 (Session 28)_

## What I observed in the replay

Downloaded and analyzed three v52 online replays (best=52.4, median=34.3, worst=6.3):

- **Best match (with slanky:v171)**: 241 junctions captured, 524K held, 0 deaths, gear stable (0.5 changes/agent), max stuck 14 steps. Agents are highly productive when the partner is strong and clips pressure is low.
- **Median match (with ron.calib.mid_b)**: 167 junctions, 343K held, 10.1 deaths/agent, 2.5 gear changes/agent. Moderate performance — gear churn wastes ~250-500 steps per agent.
- **Worst match (with dedicated.ao)**: 26 junctions, 63K held, 5 deaths, 5.5 gear changes/agent, scout gear picked up (0.375/agent), max stuck 410 steps. Agents are losing gear constantly and getting stuck for 4% of the game at a time.

The #1 controllable factor separating good from bad matches is **gear contamination**: agents stepping on wrong-type stations during navigation.

## Current bottleneck

**Gear contamination in adversarial matches.** In worst-case matches, agents lose and re-acquire gear 5+ times each, costing 500-1000 steps total per agent (out of 10,000). This directly causes the 6.3 score floor. Fixing this would lift the floor from ~6 to ~15-20 and improve the median from 34.3 to ~37+.

Secondary bottleneck: JUNCTION_ALIGN_DISTANCE=20 causes agents to target junctions too far from their aligned network. C4lUC showed that 15 reduces move failures by 28%.

## What I expected to happen vs. what I found

**Expected**: Session 27 reverted main to v52. I expected new researcher branches to build on the clean v52 baseline.

**Found**: Two branches (C4lUC, q8Otj) worked since session 27, but both forked BEFORE the revert and contain hCVEi code. They can't be merged. The q8Otj experiments (wider distances) go in the wrong direction. The C4lUC experiments (JUNCTION_ALIGN_DISTANCE=15, explore_beyond_aligned) have good ideas that should be reimplemented on v52.

**Found**: v52 dropped from #33 to #36 (35.89 vs 36.11) — natural drift as 633 entries now exist (was 565). Not a code regression.

**Found**: No new policy was submitted since session 27. We're stalling. The next researcher needs to make progress on v52 baseline.

## Issues updated this session

- **#64**: CREATED (priority:1) — Gear contamination prevention. The replay-evidenced #1 tractable problem.
- **#62**: COMMENTED — Added replay analysis, recommended experiment order (JUNCTION_ALIGN_DISTANCE=15 first, explore_beyond second, gear contamination third)
- **#50**: DEMOTED to priority:2 — Low-hanging fruit exhausted per the issue's own comments. Primary target achieved (>36.0).
- **#63**: Already closed (revert completed in session 27)

## Branches NOT merged (and why)

- **C4lUC** (ae4e263): Contains hCVEi code. Good ideas (JUNCTION_ALIGN_DISTANCE=15, explore_beyond_aligned) need reimplementation on v52.
- **q8Otj** (17bab23): Contains hCVEi code. Wider distances (30/40/30) contradict evidence — previous experiments showed wider distances regress.
- All other branches predate the v52 revert and are stale.

## Submission status

- **beta-cvc**: v52:v1 is live at #36 (35.89). No new submission warranted — nothing beats v52.
- **beta-teams-tiny-fixed**: We have NO entries. Only 10 entries exist (scores 10-26). Should submit v52 there for free ranking. Researcher should run: `cogames submit lessandro-scripted-v52:v1 --season beta-teams-tiny-fixed`

## Open questions for next director

1. **Will JUNCTION_ALIGN_DISTANCE=15 improve online?** C4lUC showed +5% offline on seed 42 with -28% move failures. This is the lowest-risk change to try. If a researcher implements and validates this, it should be submitted.
2. **Can gear contamination be fixed without adding complexity?** The key lesson from v59 is that "safety net" state machines (blacklisting, rotation, switchable miner) regress online even when they show "no regression" offline. The fix must be BFS-level (add stations to blocked_cells), not policy-level (new state variables).
3. **Should we clean up old branches?** There are 70+ remote branches. Most predate v52 and are stale. Cleaning them would reduce confusion for new researchers.
4. **The partner variance problem**: v52 scores 6.3-52.4 depending on partner (8x range). Top RL policies likely have lower variance. Can we reduce our floor without hurting ceiling? Gear contamination prevention (#64) is the best bet.
5. **RL training (#41)**: Still blocked on GPU. This remains the theoretical ceiling-breaker but no infrastructure exists. If someone gets Bazel + mettagrid building, the RL path opens up.
