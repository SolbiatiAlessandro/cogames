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
