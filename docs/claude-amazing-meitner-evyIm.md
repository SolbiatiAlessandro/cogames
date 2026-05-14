# Autoresearch: Issue #73 - A/B Test toEqP Improvements (Session evyIm)

## Context
Issue #73 asks us to isolate and A/B test individual toEqP changes online. The previous session (AX5WP) uploaded 7 variants but WITHOUT `--season beta-cvc`, so they got 0 matches. My job is to re-upload them properly and monitor results.

Current standing: navfix-cd3:v1 = #17 at 40.32 on beta-cvc leaderboard.
Target: online score > 41.0

## Variants to test (each changes ONE thing from navfix-cd3 baseline):
| Variant | Change | Code location |
|---------|--------|---------------|
| A: stuck15 | stuck_threshold=15 (was 20) | init_kwarg |
| B: 5a3m | num_aligners=5 (was auto=4) | init_kwarg |
| C: hub30 | HUB_ALIGN_DISTANCE=30 (was 25) | aligner_agent.py:24 |
| D: enemy | Enemy recapture priority -8 in junction scoring | aligner_agent.py:734 |
| E: hpret65 | HP_RETREAT_THRESHOLD=0.65 (was 0.70) | aligner_agent.py:31 |
| F: spread | Spread bonus -0.05 * min(dist,30) in junction scoring | aligner_agent.py:734 |

## 2026-05-14T17:10: autoresearch starting

My plan is to:
1. Run baseline offline to confirm numbers
2. Re-upload all 7 variants with --season beta-cvc so they enter matchmaking
3. Run offline experiments for each variant to have comparison data
4. Monitor online match results as they accumulate
5. Post findings to issue #73

## 2026-05-14T17:10: starting to run baseline

Cannot run offline episodes in this environment (mettagrid 0.15.0 requires Python 3.12 + Bazel build, TLS issues in sandbox). Pivoting to online-only A/B testing.

## 2026-05-14T17:15: uploading A/B test variants to beta-cvc

Previous session (AX5WP) uploaded 7 variants WITHOUT `--season beta-cvc`, resulting in 0 matches.
Re-uploaded all variants WITH `--season beta-cvc` — all confirmed "Submitted to pools: ['qualifying']".

| Policy Name | Change | Policy ID | Status |
|-------------|--------|-----------|--------|
| `evyIm-baseline` | None (clean navfix-cd3) | `ee3d1799` | qualifying |
| `evyIm-73a-stuck15` | stuck_threshold=15 (was 20) | `5add7dea` | qualifying |
| `evyIm-73b-5a3m` | num_aligners=5 → 5A+3M (was 4A+4M) | `8ac1934b` | qualifying |
| `evyIm-73c-hub30` | HUB_ALIGN_DISTANCE=30 (was 25) | `5bbde7b2` | qualifying |
| `evyIm-73d-enemy` | Enemy recapture priority -8 | `2dd0beef` | qualifying |
| `evyIm-73e-hpret65` | HP_RETREAT_THRESHOLD=0.65 (was 0.70) | `b6ca96ae` | qualifying |
| `evyIm-73f-spread` | Spread bonus -0.05×min(dist,30) | `b15487fb` | qualifying |
| `evyIm-73g-stuck15-hpret65` | stuck15 + HP retreat 0.65 combo | `9258eece` | qualifying |
| `evyIm-73h-5a3m-stuck15` | 5A+3M + stuck15 combo | `9747c4d0` | qualifying |

**Why combos**: toEqP showed stuck_threshold and HP retreat were the two biggest individual deltas offline (+10.3% and +19.0%). Testing combos early to see if they stack or interact online.

Now waiting for qualifying matches to complete. Each policy needs to pass qualification before entering the competition pool where scores are measured.

## 2026-05-14T17:25: uploaded additional variants based on ax5wp findings

Read ax5wp session 2-3 comments on issue #71. Key findings contradict issue #73 assumptions:
- 5A+3M is **bad** (-7.4% offline) — we already uploaded it as variant B, will validate
- stuck_threshold=15 is **bad** (-1.3%) — already variant A
- 2A+6M is the BEST ratio (+12.2%)
- HUB_ALIGN=35 is better than 30 (+6.4% vs +2.7%)
- patience=10 (heart wait steps) is +19.5%

Additional uploads:
| Policy Name | Change | Policy ID |
|-------------|--------|-----------|
| `evyIm-73i-hub35` | HUB_ALIGN_DISTANCE=35 only | `8b58b222` |
| `evyIm-73j-2a6m` | num_aligners=2 (2A+6M) only | `a570e754` |
| `evyIm-73k-patience10` | Heart wait patience=10 (was 3) | `3575dd29` |
| `evyIm-73L-fullbest` | HUB=35 + spread + enemy + 2A+6M + patience=10 | `c3d88b8c` |

Total: 13 policies in beta-cvc qualifying pool (1 baseline + 6 individual + 2 combos from #73 + 4 from ax5wp insights).

Also uploaded two more 5A+3M combos based on early results (5A+3M scored 45.08 in first qualifying match!):
- `evyIm-73m-5a3m-hub30`: 5A+3M + HUB_ALIGN=30
- `evyIm-73n-5a3m-patience10`: 5A+3M + patience=10

## 2026-05-14T17:35: early qualifying results (VERY preliminary, 1-2 matches each)

| Variant | Avg Score | Matches | vs navfix-cd3 (40.32) | Signal |
|---------|-----------|---------|----------------------|--------|
| **73b-5a3m** | **45.08** | 1 | **+11.8%** | STRONG positive |
| 73d-enemy | 41.87 | 2 | +3.8% | Positive |
| baseline | 41.77 | 1 | +3.6% | Baseline OK |
| 73e-hpret65 | 41.77 | 1 | +3.6% | Neutral |
| 73f-spread | 41.77 | 1 | +3.6% | Neutral |
| 73g-stuck15-hpret65 | 39.67 | 1 | -1.6% | Negative |
| **73h-5a3m-stuck15** | **30.33** | 1 | **-24.8%** | **STRONG negative** |

Early findings:
1. **5A+3M alone is AMAZING online** (45.08) — contradicts ax5wp's -7.4% offline finding
2. **5A+3M + stuck15 combo is TERRIBLE** (30.33) — stuck15 destroys 5A+3M benefit
3. Enemy recapture priority shows moderate positive signal
4. HP retreat 0.65 and spread bonus appear neutral vs baseline
5. stuck15+hpret65 combo is slightly negative

CAUTION: These are qualifying self-play matches (1-2 per variant). Need 10+ competition matches to judge.
