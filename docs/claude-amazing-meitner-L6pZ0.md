# Experiment Log: claude/amazing-meitner-L6pZ0 (Issue #58 continuation)

## Goal
Improve 2-agent online scores (currently avg ~15.4 in v4) to reach overall score > 36.0.

## Context
- v4 online 2-agent scores: 22.22, 21.54, 20.00, 16.19, 11.34, 8.83, 7.79 (avg ~15.4)
- v4 online 4-agent avg: ~39.6 (good)
- v4 online 6-agent avg: ~34.5
- Current best overall: v52 at 35.57 (#33), bekkenze:v1 at 35.00 (#39)
- Target: overall > 36.0, 2-agent avg > 25.0

---

2026-05-03T00:00: autoresearch starting, my plan is to:
1. Analyze 2-agent online failure modes from v4 data
2. Implement adaptive behavior based on team size (n_agents <= 2)
3. Key hypothesis: when we only have 2 agents, we need to:
   - Be more patient at hub (opponents deposit too, hearts will come)
   - Fail over from miner to aligner faster (less idle time)
   - Explore wider when extractors are contested
   - Reduce defend duration (can't afford idle agents)
4. Run CvC baseline, then iterate

2026-05-03T00:01: starting to run baseline

2026-05-03T01:00: CvC baseline (5 seeds, 2000 steps, 8 agents):
- seed 42: 1126.0
- seed 123: 1096.0
- seed 7: 1228.0
- seed 99: ~1100
- seed 256: ~1100

2026-05-03T01:30: Implemented adaptive miner thresholds for small teams (<=2 agents):
- fast_depletion_threshold: 3 (vs 5 for larger teams)
- drought_threshold: 500 (vs 1000 for larger teams)
- SwitchableMiner clear_threshold: 3 (vs 5)
- SwitchableMiner switch_threshold: 5 (vs 8)
- Team size tracked at runtime via SharedMap.all_agent_ids

2026-05-03T02:00: Verified NO CvC regression — all 5 seeds match baseline
(Changes only activate when _n_team_agents <= 2, which never happens in 8-agent CvC)

2026-05-03T02:30: Verified NO 8-agent regression — seeds 42/123/7: 1126/1096/1228

2026-05-03T03:00: Tried and REVERTED aligner changes (all regressed CvC):
- Hub depletion threshold 1→3: REGRESSED (60.52→36.74) — hub IS depleted with slow hearts
- Defend duration 500→200: REGRESSED (→48.15) — not enough time for heart accumulation
- Explore during defend: REGRESSED (→55.26) — moves aligner away from hub
- Skip unstuck: REGRESSED — needed for normal operation

CONCLUSION: Aligner changes cannot be validated offline. CvC starters create different
hub dynamics than online opponents. Miner-only changes are safe because they target
scenarios (contested extractors, blocked stations) that don't occur vs starters.

2026-05-03T03:30: Current commit: 3c8d1e3 — miner-only adaptive thresholds
Next: submit online and test against real opponents in 2-agent matches.
