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

## 2026-05-14: Online results — FULL LEADERBOARD SNAPSHOT

### All issue-73 variants (beta-cvc qualifying)
| Policy | Rank | Score | Matches | Raw Avg | Change |
|--------|------|-------|---------|---------|--------|
| **ax5wp-73j-enemy-hub30** | **#1** | **48.75** | 6 | 39.71 | enemy-8 + HUB30 |
| ax5wp-73d-enemy | #19 | 40.58 | 16 | 38.80 | enemy -8 |
| lessandro-navfix-cd3 | #20 | 40.39 | 29 | 40.10 | BASELINE |
| ax5wp-73c-hub30 | #24 | 40.06 | 16 | 39.45 | HUB_ALIGN=30 |
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

### Key findings from match data analysis

**ax5wp-73j-enemy-hub30 (#1, score 48.75)**: Only 6 matches — score is INFLATED by rating algorithm.
- Raw scores: [48.75, 43.74, 43.25, 41.60, 40.04, 20.86]
- Raw avg = 39.71 (below baseline's 40.10)
- Rating system hasn't converged — #1 ranking is unreliable

**ax5wp-73d-enemy (#19, score 40.58)**: Recovered from #27 as more matches complete.
- 16 matches, raw avg 38.80 (dragged by 1.07 outlier with broken partner)
- Excl. 1.07: avg 41.31 (15 matches) — marginally better than baseline
- Enemy priority is the ONLY isolated change showing positive signal online

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
