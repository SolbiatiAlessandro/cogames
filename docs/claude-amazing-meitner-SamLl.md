# Experiment Log: claude/amazing-meitner-SamLl

## Issue: #62 — Junction capture rate & exploration coverage (Tier 2: Navigation efficiency)

### Focus: Reducing aligner move failure rate

The #67 analysis found that 33% of aligner steps are move failures — the strongest predictor of match score. Good matches have 178 failures vs 742 in bad matches. This is the #1 remaining lever for improving online performance.

Current best online: opt-v1 at #14 (39.72) with JUNCTION=25, hearts<3, wait<3, contamination code.

---

## 2026-05-10T00:00: autoresearch starting

Plan:
1. Run baseline to establish current performance (5-seed avg)
2. Analyze move failure patterns in logs
3. Experiment with navigation improvements:
   - Better cooldown management (6-tick cooldown may be suboptimal)
   - Agent collision avoidance using SharedMap.agent_positions
   - Smarter BFS fallback when path is blocked
   - Path memory for known routes (hub→junction, station→hub)
4. Target: reduce move failures from ~33% to <15%, improve mission reward

## 2026-05-10T00:01: starting to run baseline

## 2026-05-10T06:30: Exp 1 — Agent-aware BFS (ABANDONED)

Tested teammate-aware BFS in three variants:
- 1a: Stuck escape in base class → NO EFFECT (dead code — LLMAlignerPolicyImpl overrides step_with_state)
- 1b: Unblock all teammate positions → +1.7% avg but -7.3% on seed 123, too inconsistent
- 1c: Unblock teammates >3 cells away → -0.03% avg, regression

All reverted to baseline.

## 2026-05-10T06:38: Exp 2a — JUNCTION_ALIGN_DISTANCE=15 fix (KEPT)

**Hypothesis**: `_JUNCTION_ALIGN_DISTANCE=25` in aligner policy mismatches game engine's cascade distance of 15. Aligners waste time traveling to junctions 16-25 cells from friendly network where cascade alignment silently fails.

**Fix**: Split into `_JUNCTION_ALIGN_DISTANCE=15` (used in `_is_alignable()`) and `_JUNCTION_EXPLORE_DISTANCE=25` (used in `_alignment_frontier_cells()` for exploration).

**Results**: +2.5% avg (137.02→140.46), all 5 seeds positive, move failures -12.5%

| Seed | Baseline | Fix | Delta |
|------|----------|-----|-------|
| 42 | 130.05 | 133.44 | +3.39 |
| 123 | 133.94 | 136.33 | +2.39 |
| 7 | 137.90 | 143.36 | +5.46 |
| 99 | 135.20 | 139.31 | +4.11 |
| 555 | 148.01 | 149.88 | +1.87 |

Confirms findings from two prior researchers (#67 OPj3g, #65 IgXg8). **KEEPING this change.**
