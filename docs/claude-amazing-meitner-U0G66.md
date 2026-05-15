# Experiment Log: claude-amazing-meitner-U0G66

## Issue: #73 — Isolate and A/B test toEqP improvements

### 2026-05-15 00:00: Autoresearch starting

My plan is to:
1. Run baseline (navfix-cd3, commit 14c7ac6) to establish current reward
2. Implement the 75c combo changes that achieved #3 online (42.66):
   - Hub L2 fix in `_is_alignable`
   - Enemy recapture priority (-8) in `_cascade_priority_target`
   - Spread exploration (`_pick_spread_frontier`)
   - Defend timeout reduction (×10 instead of ×50)
   - Heart retry threshold ≥2
3. Validate offline improvement
4. Try additional structural improvements:
   - Dynamic target switching when enemy presence detected
   - Phase-based strategy (claim vs hold modes)
   - Stuck threshold tuning in combination with 75c changes
5. Upload best variant to tournament

### 2026-05-15 00:01: Baseline results (commit 14c7ac6)

| Seed | Reward |
|------|--------|
| 42 | 1026.80 |
| 43 | 1068.33 |
| 44 | 1177.92 |
| 45 | 1141.58 |
| 46 | 1093.82 |
| **Avg** | **1101.69** |

### 2026-05-15 00:10: 75c combo implementation

Applied 5 changes from the ax5wp-75c variant that achieved #3 online (42.66):
1. Hub L2 fix in `_is_alignable` — Euclidean instead of Manhattan for hub distance
2. Enemy recapture priority (-8) in `_cascade_priority_target`
3. Spread exploration (`_pick_spread_frontier` with 0.5 other-agent penalty)
4. Defend timeout ×10 (200 steps instead of 1000)
5. Heart retry threshold ≥2

**Result**: 5-seed avg = 1137.95 (+3.3%)

| Seed | Baseline | 75c combo | Delta |
|------|----------|-----------|-------|
| 42 | 1026.80 | 1059.21 | +3.2% |
| 43 | 1068.33 | 1080.54 | +1.1% |
| 44 | 1177.92 | 1233.26 | +4.7% |
| 45 | 1141.58 | 1195.02 | +4.7% |
| 46 | 1093.82 | 1121.75 | +2.6% |
| **Avg** | **1101.69** | **1137.95** | **+3.3%** |

### 2026-05-15 00:20: Parameter sweeps

| Experiment | 5-seed avg | vs baseline | vs 75c-0.05 | Status |
|-----------|-----------|-------------|-------------|--------|
| 75c + stuck_threshold=15 | 1099.47 | -0.2% | -3.4% | discard |
| 75c + HP retreat 0.65 | 1137.95 | +3.3% | 0% | keep (online-only) |
| 75c + junction spread=0.10 | **1150.66** | **+4.4%** | **+1.1%** | **BEST** |
| 75c + junction spread=0.15 | 1123.76 | +2.0% | -1.2% | discard |
| 75c + explore spread=0.3 | 1132.45 | +2.8% | -0.5% | discard |
| 75c + explore spread=0.7 | 1129.76 | +2.5% | -0.7% | discard |
| 75c + heart accumulation <4 | 1136.04 | +3.1% | -0.2% | discard |
| 75c + explore cap=30 | 1141.08 | +3.6% | +0.3% | noise |
| 75c + enemy recapture -5 | 1150.66 | +4.4% | 0% | no effect in self-play |
| 75c + miner spread explore | 1118.59 | +1.5% | -2.8% | discard |
| 75c + L2 frontier alignment | 1122.06 | +1.8% | -2.5% | discard |

Best config: 75c + junction spread=0.10, explore spread=0.5

Key findings:
- Enemy recapture is purely online-relevant (no enemy junctions in self-play)
- HP retreat changes are online-relevant (no HP drain in self-play)
- Junction spread=0.10 is optimal (0.05 too weak, 0.15 too strong)
- Stuck_threshold=15 destructively interacts with 75c changes
- Miner improvements hurt — miners need proximity to extractors

### 2026-05-15 00:45: Preparing upload and further experiments
