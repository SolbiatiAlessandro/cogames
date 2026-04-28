# Experiment Log: Issue #52 — Validate v49 online performance and submit v50

## 2026-04-28T10:30: Autoresearch starting

**Issue**: #52 — Validate v49 online performance and submit v50 if needed
**Branch**: claude/amazing-meitner-b3onP
**Plan**: Check v49 online scores, diagnose regression vs v48, then submit v50 with fixes.

## 2026-04-28T10:31: v49 online results — REGRESSION

v49 has 25 matches. v48 has 44 matches.

| Version | Rank | Score | Avg Match | Min | Max |
|---------|------|-------|-----------|-----|-----|
| v48 | #54 | 32.94 | 29.96 | 4.90 | 50.12 |
| v49 | #71 | 30.58 | 27.91 | 2.31 | 45.42 |

**v49 regressed**: rank dropped from #54 to #71, score from 32.94 to 30.58.

v49 key changes over v48:
1. Phantom aligner station fix (verified_aligner_stations)
2. Phantom hub fix (verified_hubs for aligners + miners)
3. BFS cooldown bypass (aligner + miner)
4. stuck_threshold 20→15
5. hub_dist 0.3→0.2, max_hearts 3→4, 3A+5M static IDs

Hypothesis for regression: stuck_threshold=15 may be too aggressive in online play where partner behaviors are unpredictable. Also, 3A+5M static allocation may hurt when paired with partners that already have many aligners/miners.

**Next step**: Investigate code, run baseline offline, then try v50 with stuck_threshold=20 as control.

## 2026-04-28T17:28: Baseline results (current code = v48 codebase)

3-seed baseline at 3000 steps, 8 agents, stuck_threshold=20 (default), 5A+3M (auto):

| Seed | Total Reward | Avg/Agent |
|------|-------------|-----------|
| 42 | 826.43 | 103.30 |
| 123 | 799.25 | 99.91 |
| 7 | 984.32 | 123.04 |
| **Avg** | **869.99** | **108.75** |

Key finding: v49 phantom fixes were on a different branch (commit 9001d58) never merged to main. Current HEAD (cbbc1e9) is essentially v48's codebase. The v49 regression was likely caused by:
1. stuck_threshold=15 (known suboptimal from MGrvP parameter sweep: 20=6.46 vs 15=6.23)
2. 3A+5M static IDs (vs 5A+3M auto which was proven better in pzwh4)

**Plan**: Submit v50 as control with current code + optimal defaults, then iterate on improvements.
