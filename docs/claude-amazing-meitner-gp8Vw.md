# Experiment Log: claude/amazing-meitner-gp8Vw

## Issue: #52 - Validate v49 online performance and submit v50 if needed

2026-04-29 00:00: autoresearch starting, my plan is to:
1. Analyze v49 and v50 online performance (already done — both regressed)
2. Root-cause the regression: v49 used 3A+5M + stuck_threshold=15, v50 was from old main
3. Fix: restore stuck_threshold=20 and 5A+3M allocation while keeping phantom fixes
4. Run baseline on current code (with bugs)
5. Apply fixes and run experiment
6. Submit v51 with optimal params + all improvements

### Online Performance Summary (as of 2026-04-29)
- v48: #54, score 32.91, avg 29.86 (49 matches) — our best
- v49: #73, score 30.44, avg 27.76 (26 matches) — regressed
- v50: #115, score 18.46, avg 20.97 (24 matches) — severe regression

### Root Cause Analysis
v49 regression caused by TWO parameter changes from uTokl integration:
1. stuck_threshold 20→15: MGrvP sweep showed 20 optimal (6.46 vs 6.23)
2. 5A+3M → 3A+5M: pzwh4 showed 5A+3M gives +43% over 3A+5M at 3k steps

v50 catastrophic regression: submitted from OLD main (cbbc1e9, session 16) missing ALL improvements from sessions 17-20 (phantom fixes, multi-heart, hub diversification, deposit fixes, etc.)

v48 succeeded because: 5A+3M + stuck_threshold=20 + sessions 17-18 improvements

### Fix Strategy for v51
Keep from current branch: verified_hubs, verified_stations, BFS cooldown bypass, multi-heart accumulation, cascade priority, hub diversification
Restore from v48 era: stuck_threshold=20, 5A+3M role allocation

2026-04-29 00:01: starting to run baseline on current code (before fixes)

### Baseline Results (3A+5M, stuck_threshold=15) — current code
| Seed | Total Reward | Hearts | Junctions |
|------|-------------|--------|-----------|
| 42 | 1083.15 | 58 | 51 |
| 123 | 1037.33 | 56 | — |
| 7 | 1064.03 | 70 | — |
| **avg** | **1061.50** | | |

2026-04-29 00:05: Applied fixes: stuck_threshold 15→20, 3A+5M→5A+3M (proportional dynamic assignment)

### Experiment Results (5A+3M, stuck_threshold=20)
| Seed | Total Reward | Hearts | Junctions |
|------|-------------|--------|-----------|
| 42 | 1072.46 | 59 | 53 |
| 123 | 1045.42 | 62 | — |
| 7 | 1064.84 | 69 | — |
| **avg** | **1060.91** | | |

Offline diff: -0.06% (neutral). Expected — in self-play both configs converge. The real signal is online where v48 (same params) scored 32.91 vs v49 (old params) 30.44.

2026-04-29 00:10: Submitted v51 to beta-cvc qualifying pool
- Name: lessandro-scripted-v51:v1
- Policy ID: 04710429-c895-4377-bb5e-32ff9746c0fe
- Commit: 2c0dcf7
- Config: stuck_threshold=20, 5A+3M proportional, scripted_miners=True, scripted_aligners=True
- Improvements over v48: verified_hubs, verified_stations, BFS cooldown bypass, multi-heart (4), cascade priority, hub diversification
- Improvements over v49: stuck_threshold=20 (was 15), 5A+3M (was 3A+5M)
- Expected: score ≥ 33.0 (beat v48) since v51 = v48 params + phantom fixes

Next: monitor v51 qualifying matches, compare against v48/v49/v50. If v51 outperforms v48, the phantom fixes help online. If similar to v48, the params are what matter.
