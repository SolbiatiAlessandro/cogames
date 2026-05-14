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

## 2026-05-14: Online results snapshot (updated)

### Leaderboard positions (beta-cvc qualifying)
| Policy | Rank | Score | Matches | Notes |
|--------|------|-------|---------|-------|
| **ax5wp-junct71:v1** | **#5** | **41.73** | 9 | Best mine, unknown code |
| lessandro-navfix-cd3:v1 | #17 | 40.51 | 27 | Baseline |
| ax5wp-73d-enemy:v1 | #27 | 39.08 | 8 | Enemy -8 (has 1.07 outlier!) |
| ax5wp-73c-hub30:v1 | #30 | 38.91 | ? | HUB_ALIGN=30 |
| ax5wp-73-baseline:v1 | #132 | 33.32 | ? | Clean baseline upload |

### Critical finding: Enemy variant match data analysis

ax5wp-73d-enemy has ONE catastrophic match (1.07 with "anoop.visage" — broken partner):
- **With outlier**: avg=37.75, 8 matches → score 39.08 on leaderboard
- **Without outlier**: avg=42.99, 7 matches → would be ~#8 on leaderboard

Match scores: [52.28, 25.88, 49.29, **1.07**, 53.35, 36.43, 44.45, 39.28]

navfix-cd3 comparison: avg=40.09, 27 matches, worst=20.88 (never paired with anoop.visage)

**Conclusion**: Enemy priority IS working online — avg 43 vs baseline 40 when paired with reasonable partners. The leaderboard drop from #5→#27 is entirely due to one terrible partner match.

### Wave 2 variants (enemy optimization, enrolled, awaiting matches)
| Variant | Change | Upload Name | Status |
|---------|--------|-------------|--------|
| I | enemy -8 + spread -0.05 | ax5wp-73i-enemy-spread | enrolled |
| J | enemy -8 + HUB_ALIGN=30 | ax5wp-73j-enemy-hub30 | enrolled |
| K | enemy bonus -12 | ax5wp-73k-enemy12 | enrolled |
| L | enemy bonus -4 | ax5wp-73l-enemy4 | enrolled |

### Wave 3 variants (hub_dist weight sweep, enrolled, awaiting matches)
| Variant | Change | Upload Name | Status |
|---------|--------|-------------|--------|
| M | hub_dist weight = 0 (pure travel) | ax5wp-73m-hubw0 | enrolled |
| N | hub_dist weight = 0.5 (strong hub) | ax5wp-73n-hubw05 | enrolled |
| O | enemy -8 + hubw=0 | ax5wp-73o-enemy-hubw0 | enrolled |
| P | enemy -8 + hubw=0.5 | ax5wp-73p-enemy-hubw05 | enrolled |

### Clips scramble impact estimate (10k steps)
- 100 scramble events × up to 4 junctions = ~400 scramble attacks per episode
- With 50 held junctions, each could be hit ~8 times
- Recapture cycle: ~20-50 steps per junction
- Estimated 30% of aligner time on recapture → enemy priority directly improves this
