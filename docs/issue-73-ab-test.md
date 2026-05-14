# Issue #73: A/B Test toEqP Improvements Online

## Baseline (navfix-cd3 / main)
- HUB_ALIGN_DISTANCE = 25
- HP_RETREAT_THRESHOLD = 0.70
- stuck_threshold = 20
- aligner_fraction = 0.5 (4A+4M)
- patience (no_progress_on_target_steps) < 3
- Junction scoring: travel + hub_dist * 0.2 (no spread/enemy bonus)

## 2026-05-14: autoresearch starting

Plan: Upload 6 isolated variants to beta-cvc tournament, each changing exactly one parameter from the navfix-cd3 baseline.

### Variants
| Variant | Change | Upload Name |
|---------|--------|-------------|
| A | stuck_threshold=15 | ax5wp-73a-stuck15 |
| B | 5A+3M (num_aligners=5) | ax5wp-73b-5a3m |
| C | HUB_ALIGN_DISTANCE=30 | ax5wp-73c-hub30 |
| D | enemy recapture priority (-8) | ax5wp-73d-enemy |
| E | HP retreat 0.65 | ax5wp-73e-hpret65 |
| F | spread bonus (-0.05) | ax5wp-73f-spread |
| G | patience=10 (heart wait) | ax5wp-73g-patience10 |
| H | HUB35 + 2A6M + patience10 (combo) | ax5wp-73h-combo-safe |

All 8 variants + baseline enrolled in beta-cvc qualifying pool.

## Offline validation (seed 42, 3k steps, navfix-cd3 code)

Critical finding: **individual changes REGRESS on clean main code**.

| Variant | Seed 42 reward | vs baseline (1026.80) |
|---------|---------------|----------------------|
| Baseline (main) | 1026.80 | — |
| G: patience=10 | 956.52 | **-6.8%** |
| 2A+6M (num_aligners=2) | 940.00 | **-8.5%** |
| C: HUB_ALIGN=35 | 1012.14 | **-1.4%** |

5-seed validation of spread+enemy combo (D+F together):

| Seed | Baseline | Spread+Enemy | Delta |
|------|----------|-------------|-------|
| 42 | 1026.80 | 1067.81 | +4.0% |
| 43 | 1068.33 | 1035.86 | -3.0% |
| 44 | 1177.92 | 1189.45 | +1.0% |
| 45 | 1141.58 | 1161.22 | +1.7% |
| 46 | 1093.82 | 1093.12 | -0.06% |
| **Avg** | **1101.69** | **1109.49** | **+0.7%** |

Conclusion: Spread+enemy combo is within noise on navfix-cd3.
Changes that helped in earlier sessions (with HUB35+2A6M+patience10) don't help individually on clean main.
The online A/B tests are the decisive signal.

## 2026-05-14 19:30: Converged online results (CRITICAL UPDATE)

### Raw avg vs leaderboard divergence
With 20+ matches per variant, raw averages are converging and tell a DIFFERENT story than leaderboard ranks (which use Elo/TrueSkill, not raw avg).

| Policy | Rank | Score | Matches | Raw Avg | vs baseline |
|--------|------|-------|---------|---------|-------------|
| evyIm-73a-stuck15 | #5 | 41.85 | ~9 | 37.99 | different codebase? |
| **ax5wp-73j-enemy-hub30** | **#11** | **40.95** | **21** | **39.47** | **closest to baseline** |
| lessandro-navfix-cd3 | #18 | 40.49 | 29 | 40.10 | BASELINE |
| ax5wp-73d-enemy | #31 | 39.16 | 21 | **36.46** | **-3.64 pts!** |
| ax5wp-73c-hub30 | #26 | 39.35 | 16 | 39.45 | -0.65 pts |
| ax5wp-73i-enemy-spread | #29 | 39.34 | ? | ? | enemy-8 + spread |
| ax5wp-73n-hubw05 | #34 | 38.97 | ? | ? | hubw=0.5 |
| ax5wp-73m-hubw0 | #39 | 38.75 | ? | ? | hubw=0 |
| ax5wp-73-baseline | #53 | 37.87 | ? | ? | clean baseline |
| ax5wp-73o-enemy-hubw0 | #64 | 37.19 | ? | ? | enemy + hubw=0 |
| ax5wp-73g-patience10 | #65 | 37.18 | ? | ? | patience=10 |
| ax5wp-73e-hpret65 | #76 | 36.66 | ? | ? | HP retreat 0.65 |
| ax5wp-73l-enemy4 | #82 | 36.33 | ? | ? | enemy -4 |
| ax5wp-73f-spread | #90 | 36.12 | ? | ? | spread -0.05 |
| ax5wp-73a-stuck15 | #155 | 33.20 | 20 | 30.69 | stuck=15 |
| ax5wp-73p-enemy-hubw05 | #160 | 33.02 | ? | ? | enemy + hubw=0.5 |
| ax5wp-73h-combo-safe | #170 | 32.45 | ? | ? | hub35+2a6m+pat10 |
| ax5wp-73b-5a3m | #189 | 31.35 | ? | ? | 5A+3M |
| ax5wp-73k-enemy12 | #736 | 8.20 | ? | ? | enemy -12 |

### CRITICAL FINDING: No variant beats baseline by raw average

With 20+ matches per variant, the initial positive signals have evaporated:
- **enemy -8 alone**: 21 matches, raw avg 36.46 (BELOW baseline 40.10)
- **enemy-hub30 combo**: 21 matches, raw avg 39.47 (closest, but still -0.63)
- **L2 fix + enemy**: 19 matches, raw avg 35.47 (significantly worse)
- **L2 fix + enemy + hub30**: 17 matches, raw avg 32.45 (catastrophic)
- **L2 fix alone**: 4 matches, raw avg 39.60 (too early to judge)

The leaderboard ranks (Elo/TrueSkill) tell a different story — enemy-hub30 at #11 vs baseline at #18. This suggests the rating system adjusts for partner quality, which benefits enemy-hub30 more than raw average shows.

**Bottom line**: navfix-cd3 remains our strongest policy. No code changes tested improve raw online performance. The scoring function (travel + hub_dist × 0.2) in the baseline is already well-calibrated.

**ax5wp-73k-enemy12 (#736, 8.20)**: Too-aggressive enemy bonus is catastrophic.
- Enemy -12 bonus is too strong, distorts all targeting decisions
- Confirms -8 is near the right ballpark, -12 is way past it

### Pattern from hub_dist weight sweep
| hubw | Score | Rank | Notes |
|------|-------|------|-------|
| 0.0 | 38.75 | #39 | Below baseline |
| 0.2 | 40.39 | #20 | Baseline |
| 0.5 | 38.97 | #34 | Below baseline |
| enemy+hubw0 | 37.19 | #64 | Hurts more than helps |
| enemy+hubw0.5 | 33.02 | #160 | Much worse |

**Conclusion**: Current hubw=0.2 is optimal. Higher or lower values regress online.

### L2 distance bug discovered and fixed

Game engine uses L2 distance (dr²+dc² ≤ r²) for alignment checks.
Policy used Manhattan distance (|dr|+|dc| ≤ r) with same thresholds.
- Hub (r=25): Manhattan ≤ 25 → L2 ≤ 25 always (safe, Manhattan ≤ L2)
- Cascade (r=15): Manhattan ≤ 25 vs game L2 ≤ 15 → **OVER-PERMISSIVE** by ~44%

Fixed _is_alignable to use L2 distance matching game engine exactly.
Offline: +1.3% avg (5 seeds), +7.3% on seed 42.

### Wave 4 variants (L2 fix + combos, awaiting matches)
| Variant | Change | Upload Name |
|---------|--------|-------------|
| Q | hub_dist weight = 1.0 | ax5wp-73q-hubw10 |
| R | enemy -8 + hubw=1.0 | ax5wp-73r-enemy-hubw10 |
| S | L2 distance fix only | ax5wp-73s-l2fix |
| T | L2 fix + enemy -8 | ax5wp-73t-l2fix-enemy |
| U | L2 fix + enemy -8 + hubw=1.0 | ax5wp-73u-l2-enemy-hubw10 |
| V | L2 fix + enemy -8 + HUB30 | ax5wp-73v-l2-enemy-hub30 |

### Offline validation: hub_dist weight sweep (5-seed avg)
| Weight | Seed 42 | 5-seed avg | vs baseline |
|--------|---------|-----------|-------------|
| 0.0 | 1035.19 | — | +0.8% (s42) |
| 0.2 | 1026.80 | 1101.69 | baseline |
| 0.5 | 1077.01 | — | +4.9% (s42) |
| 1.0 | 1095.33 | 1099.68 | -0.2% |
| 2.0 | 1011.92 | 1090.25 | -1.0% |

All within noise offline — online is the real test.

### Clips scramble impact estimate (10k steps)
- 100 scramble events × up to 4 junctions = ~400 scramble attacks per episode
- With 50 held junctions, each could be hit ~8 times
- Recapture cycle: ~20-50 steps per junction
- Estimated 30% of aligner time on recapture → enemy priority directly improves this

## 2026-05-15: Navigation Diagnostics & Hub L2 Fix

### Navigation diagnostic findings (seed 42, 43, 44 at 3k steps)

Instrumented aligner agents to measure move failure rates, BFS cascade usage, and time allocation.

| Metric | Seed 42 | Seed 43 | Seed 44 |
|--------|---------|---------|---------|
| Move failure rate | 3.9% | 6.0% | 12.7% |
| Stuck time | 1.3% | 2.3% | 5.8% |
| BFS primary success | 100% | 99.5% | 98.5% |
| Exploration time | 57-63% | 52-71% | 47-66% |

**Key findings:**
1. **Move failure rate is LOW (4-6%)** — NOT the bottleneck
2. **BFS succeeds 99-100% when there's a target** — navigation code is effective
3. **Exploration consumes 50-70% of aligner time** — the REAL bottleneck
4. Seed 44 agent 1: 33% fail rate, 1000 steps wasted in defend mode (pathological)

### Hub alignment geometry mismatch discovered

Game engine uses L2 distance (dr²+dc² ≤ r²) for hub alignment (r=25).
Policy used Manhattan distance (|dr|+|dc| ≤ 25) for hub filtering.

For diagonal junctions, Manhattan is MORE restrictive than L2:
- Junction at (13,13) from hub: Manhattan=26 (MISS), L2=18.4 (OK)
- Manhattan diamond inscribes the L2 circle

Analysis on seed 42 (269 total junctions, 8 hub cells):
- 101 junctions: both filters agree (hub-alignable)
- 65 junctions: initially flagged as missed but covered by other hub cells
- **23 junctions: TRULY missed by Manhattan filter** (L2 ≤ 25 but Manhattan > 25 from ALL hub cells)
- 80 junctions: both agree NOT hub-alignable

Avg distance of missed junctions: Manhattan=27.7, L2=20.4 — well within engine's range.

### Cascade false positives analysis

Policy uses Manhattan ≤ 25 for cascade (engine uses L2 ≤ 15):
- 29 false positive cascade junctions (Manhattan OK, L2 > 15)
- 0 missed cascade junctions
- Tightening cascade to L2 ≤ 15 HURTS performance (-1.5% when combined with other fixes)
- Over-permissive cascade filter provides beneficial incidental exploration

### Experiment: Hub L2 fix + defend timeout + heart retry

Three changes from baseline:
1. `_is_alignable` hub check: Manhattan → L2 distance (23 more junctions alignable)
2. Defend timeout: `stuck_threshold * 50` → `stuck_threshold * 10` (1000→200 steps)
3. Heart retry threshold: `get_heart_timeouts >= 1` → `>= 2` (more retries before defend)

| Seed | Baseline | Hub L2 only | Full combo |
|------|----------|-------------|-----------|
| 42 | 1026.80 | 1101.63 | 1101.63 |
| 43 | 1068.33 | 1050.41 | 1050.41 |
| 44 | 1177.92 | 1177.92 | 1203.67 |
| 45 | 1141.58 | 1141.58 | 1207.41 |
| 46 | 1093.82 | 1124.69 | 1124.69 |
| **Avg** | **1101.69** | **1119.25 (+1.6%)** | **1137.56 (+3.3%)** |

Cascade L2 fix tested separately: REGRESSES from +3.3% to +1.8% when added to combo.

### Online variants uploaded
| Variant | Changes | Upload Name |
|---------|---------|-------------|
| W | Hub L2 fix only | ax5wp-73w-hubl2 |
| X | Hub L2 + defend200 + HT≥2 | ax5wp-73x-hubl2-def |
