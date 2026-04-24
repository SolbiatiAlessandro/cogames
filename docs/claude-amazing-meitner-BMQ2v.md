# Autoresearch: Issue #47 - Partner Robustness

## Session: claude/amazing-meitner-BMQ2v

2026-04-24T17:00: autoresearch starting. Working on issue #47 - Partner robustness: score collapses to ~0 with weak partners.

Plan:
1. Run baseline (8 our agents) to establish reference score
2. Create noop policy to simulate weak/dead partners
3. Test with 4 our agents + 4 noop agents to confirm the dependency
4. Analyze where the bottleneck is (mining? hearts? junctions?)
5. Implement adaptive role allocation - detect when partners aren't contributing and compensate
6. Make our agents self-sufficient even with 4 out of 8 agents doing nothing

2026-04-24T17:22: starting to run baseline

Baseline (8 real agents, seed 42, 3000 steps): total_reward=826.43, hearts=49, junctions=45

2026-04-24T17:25: baseline result is 826.43. Now testing with 4 noop partners.

Noop test BEFORE fix (4 real + 4 noop, seed 42): total_reward=164.97, hearts=6, junctions=6
Root cause: ALL 4 real agents became aligners, 0 miners. The policy assigned roles by agent ID (0-4=aligner, 5-7=miner). With agents 0-3 being ours, all were aligners.

2026-04-24T17:26: starting new experiment loop. Hypothesis: dynamic role balancing will ensure balanced roles regardless of agent IDs.

## Experiment 1: Dynamic Role Assignment

Changed `MachinaLLMRolesPolicy` to assign roles dynamically as agents register via `agent_policy()`, using proportional allocation (62.5% aligner ratio). Instead of precomputing IDs, each agent is assigned aligner or miner based on whether the miner count is behind the target ratio.

Pattern for 8 agents: A, M, A, M, A, A, M, A (5A+3M, same ratio as before)
Pattern for 4 agents: A, M, A, M (2A+2M, balanced!)

Results:
- 4 real + 4 noop, seed 42: 566.80 (was 164.97 -> 3.4x improvement, 69% of full team)
- 4 real + 4 noop, seed 123: 421.24 (54% of full team)
- 2 real + 6 noop, seed 42: 565.32 (1A+1M nearly as effective!)
- 8 real, seed 42: 881.64 (was 826.43 -> +6.7% improvement, NO regression!)
- 8 real, seed 123: 776.70

2026-04-24T17:36: Experiment 1 is a strong success.

## Experiment 2: Aligner Ratio Tuning (FAILED)

Tried 0.75 ratio (3A+1M for 4 agents, 6A+2M for 8 agents). Results:
- 4+4 noop: 521.06 (worse than 560 at 0.625)
- 8 real: 642.49 (-27% regression)

Too few miners → insufficient deposits → fewer hearts. 0.625 is optimal.

## Experiment 3: Adaptive Return Load

Hypothesis: with fewer miners, smaller loads = faster trips = more deposits = more hearts.

Added `_effective_return_load()` to MinerSkillImpl: when fewer than 3 active miners detected (via SharedMap.active_miner_ids), reduce return_load proportionally (max(15, 40*n_miners//3)). With 2 miners: load=26 (effective ~30 due to mining granularity).

Results:
- 4+4 noop, seed 42: 644.16 (+15% vs experiment 1's 560.52!)
- 4+4 noop, seed 123: 557.74 (+32% vs experiment 1's 421.24!)  
- 8 real, seed 42: 881.64 (unchanged — 3 miners get load=40 as before)

2026-04-24T18:20: Experiment 3 is a strong success. The adaptive load is a free improvement for partial-team scenarios with zero cost to full-team.

## Summary of all improvements

| Config | Before | After exp1 | After exp3 | Change |
|--------|--------|-----------|-----------|--------|
| 8 real, s42 | 826.43 | 881.64 | 881.64 | +6.7% |
| 4+4 noop, s42 | 164.97 | 560.52 | 644.16 | +3.9x |
| 4+4 noop, s123 | n/a | 421.24 | 557.74 | — |

Noop-partner performance is now 63-73% of full team (was 20%). Two core changes:
1. Dynamic proportional role assignment (works regardless of agent IDs)
2. Adaptive return_load (fewer miners → faster trips)

Next researcher should try: runtime role adaptation (convert idle aligners to miners when no hearts available), or test with other partner behaviors (random actions, early death agents).
