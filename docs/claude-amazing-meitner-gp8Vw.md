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
