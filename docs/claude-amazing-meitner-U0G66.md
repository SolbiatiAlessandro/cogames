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

### 2026-05-15 00:15: Next experiments to try
- stuck_threshold=15 on top of 75c
- Phase-based strategy (claim vs hold)
- Faster initial junction claiming
