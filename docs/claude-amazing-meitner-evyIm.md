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
