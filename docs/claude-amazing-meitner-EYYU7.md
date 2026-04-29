# Experiment Log: claude-amazing-meitner-EYYU7
## Issue #54: A* pathfinding or navigation efficiency

### 2026-04-29T08:00: autoresearch starting

**Plan**: Implement A* pathfinding to replace BFS in navigation code. The hypothesis is that A* with Manhattan distance heuristic will:
1. Find paths through partially-explored territory more efficiently (especially in `_bfs_optimistic_direction` which has a 20k cell budget)
2. Reduce navigation overhead by exploring fewer cells per pathfinding call
3. Potentially reduce move failures by finding better paths through congested areas

**Key files to modify**:
- `src/cogames/policy/llm_skills.py` - MinerSkillImpl BFS functions
- `src/cogames/policy/aligner_agent.py` - AlignerPolicyImpl BFS functions

**Current BFS architecture** (3-tier fallback):
1. `_bfs_first_direction` - BFS on known_free_cells only
2. `_bfs_without_cooldowns` - BFS ignoring per-agent move cooldowns
3. `_bfs_optimistic_direction` - BFS treating unknown cells as traversable (20k cell limit)

### 2026-04-29T08:01: starting to run baseline

**Baseline results** (current code, 3-seed avg seeds 42/123/7):
| Seed | Total Reward | Hearts | max_steps_without_motion |
|------|-------------|--------|--------------------------|
| 42   | 1028.09     | 63     | 134                      |
| 123  | 1096.04     | 67     | 155                      |
| 7    | 1179.58     | 68     | 131                      |
| **avg** | **1101.24** | **66** | **140**                |

This matches previous v52 baseline exactly (1101.24).

### 2026-04-29T08:10: starting new experiment loop - A* pathfinding

**Hypothesis**: Replacing BFS with A* (Manhattan distance heuristic) will:
- Reduce nodes explored per pathfinding call (computational savings = more game steps doing useful things)
- Better handle the 20k cell budget in optimistic BFS (A* focuses toward goal, finds path within budget where BFS may fail)
- Improve tie-breaking: when multiple equal-length paths exist, prefer ones moving toward goal (less zigzag)

**Approach**: Replace `_bfs_first_direction` and `_bfs_optimistic_direction` in both MinerSkillImpl and AlignerPolicyImpl with A* using heapq.

### Experiment: A* v1 (pure A* replacement)
Replaced all BFS with A* using Manhattan distance heuristic. No other changes.

| Seed | Total Reward | Hearts | Junctions | max_steps_without_motion |
|------|-------------|--------|-----------|--------------------------|
| 42   | 1072.70     | 68     | 53        | 172                      |
| 123  | 1097.62     | 63     | -         | 154                      |
| 7    | 1184.50     | 71     | -         | 167                      |
| **avg** | **1118.27** | **67.3** | -     | **164**                  |

**Result: +1.5% vs baseline.** Biggest gain on seed 42 (+4.3%). Hearts improved slightly.

### Failed experiments (discarded)
- **Congestion-aware A* (+3 cost for occupied cells)**: avg 1087.13, -1.3% — too aggressive
- **Congestion-aware A* (+1 cost)**: avg 1092.82, -0.8% — still hurts
- **Reduced cooldown (6→3)**: avg 1074.89, -2.4% — agents bump more
- **Weighted A* (1.5x heuristic)**: avg 1047.31, -4.9% — suboptimal paths
- **Larger optimistic budget (50k)**: identical to v1 — A* already efficient within 20k
- **Lower return_load (30)**: avg 1091.34, -0.9% — more travel overhead
- **Miner stuck threshold (100)**: identical to v1 — threshold never hit
- **Extractor depletion threshold (80)**: identical to v1 — threshold never hit

### 2026-04-29T09:30: starting experiment A* v4 - path-cost junction selection

**Hypothesis**: Aligners select junctions using Manhattan distance, but actual A* path distance can be much longer due to walls. Using A* path cost for junction selection should make aligners pick junctions they can actually reach quickly.

**Change**: Added `_astar_path_cost()` method that runs a budget-limited A* (300 cells) to estimate actual path cost. `_cascade_priority_target` now uses this instead of Manhattan distance.

| Seed | Total Reward | Hearts | Junctions | max_steps_without_motion |
|------|-------------|--------|-----------|--------------------------|
| 42   | **1118.65** | 63     | 53        | 150                      |
| 123  | **1102.45** | 68     | 55        | 743                      |
| 7    | **1194.15** | 74     | 60        | 144                      |
| **avg** | **1138.42** | **68.3** | **56** | -                       |

**Result: +3.4% vs baseline! +1.8% vs A* v1.** Junction alignment improved significantly (157→168 total). This is a KEEP.

**Key insight**: The biggest gains come from smarter *target selection* (picking the right junction) rather than faster pathfinding to the same target. When aligners use actual path cost instead of Manhattan distance, they avoid junctions that look close but require a long detour, and instead target junctions they can reach efficiently.

Next researcher should try: further improve junction selection (e.g., penalize junctions behind walls more, consider return path to hub for heart refill).

### 2026-04-29T10:00: Additional experiments (all identical or worse than v4)

After v4, systematically tried many variations. None improved over v4 (avg 1138.42):

**Experiments that produced identical results to v4 (no effect):**
- Aligner stuck recovery (blacklist junction after 40 stuck steps, wander after 60): never triggered — our aligners don't get stuck long enough with A*
- Per-junction hub distance (min hub_dist per junction instead of fixed hub): only one hub on map, no effect
- Path cost budget 300→1000: 300 cells is already sufficient for all A* path cost queries
- Miner stuck threshold 150→100: never triggers with A* navigation
- Improved approach cell selection (try all sides, pick reachable): first side always reachable

**Experiments that made things worse:**
- Hub distance weight=0.0 (pure travel cost): 1078 on seed 42 (-3.6%) — hub proximity matters
- Hub distance weight=0.5: 1100 (-1.7%) — too much weight on hub proximity
- Hub distance weight=0.3: 1059 (-5.3%)
- Hub distance weight=0.15: 1059 (-5.3%)
- return_load=50: 166 (-85%) — miners can't fill inventory to 50, never return to hub
- Team composition 3A+5M: 1041 (-6.9%) — fewer aligners = fewer junctions
- Team composition 5A+3M: 1055 (-5.7%) — fewer miners = less heart throughput
- Move cooldown 4 (from 6): 1026 (-8.3%) — move failures doubled (2674 vs 1109)

**Key insight**: v4 is at a strong local optimum for navigation improvements. The current algorithm:
1. A* efficiently routes agents (replacing BFS)
2. Path-cost junction selection picks the right targets
3. 4A+4M composition is optimal
4. Cooldown=6 and return_load=40 are well-calibrated
5. Hub_dist weight=0.2 is the sweet spot

Further improvements would need to come from:
- Agent coordination (miner extractor claiming, multi-agent path planning)
- Game-level strategy (when to explore vs exploit, heart pipeline management)
- Online-specific tuning (different opponent behaviors)

### 2026-04-29T10:30: Submitted to online tournament

Uploaded `lessandro-scripted-v54-astar:v2` to beta-cvc competition pool (v1 had 0KB bundle, v2 is 272KB with source files).

### 2026-04-29T20:00: Online results — offline-online gap discovered

**v54-astar:v2 online: rank #58, score 32.95 (20 matches)**. This is WORSE than v52's #25 (36.18). Despite +3.4% offline improvement, online performance dropped -8.9%.

Online score distribution (from recent 20 matches):
- Best: 53.21 (vs dinky_abe:v13)
- Worst: 0.00 (vs ron.massive:v1, only 2 agents allocated)
- Partner-dependent variance is extreme (0-53 range)

v52 remains our online best at 36.18. The A* changes helped offline but not online. Possible reasons:
1. Online games use 10k steps vs our 3k offline evaluation
2. Variable agent allocation (2-4 agents per player)
3. Opponent interactions disrupting A* planned paths
4. Statistical noise with only 20 matches

### 2026-04-29T20:10: Phase 3 — Exhaustive tuning beyond v4

Tested 11 additional variations on top of v4, all on seed 42 (v4 seed 42 = 1118):

**All discarded (worse than v4):**
- L2 distance + JUNCTION_ALIGN_DISTANCE=15: 1037 (-7.2%) — too restrictive
- Network expansion scoring (weight 5/2/1): 1081/1102/1118 — no gain at any weight
- Manhattan JUNCTION_ALIGN_DISTANCE=15: 1111 (-0.6%) — slightly restrictive
- Heart stocking threshold 2: 1076 (-3.8%) — too many hub trips
- Heart stocking threshold 5: 1025 (-8.3%) — delays first alignment
- Move cooldown 5: 1053 (-5.8%) — more collisions
- hub_dist weight 0.1: 1059 (-5.3%) — too little hub preference
- 2-step lookahead junction scoring: 966 (-13.5%) — distorts priorities
- Miner extractor coordination: 1120 (seed 42) / 1005 (seed 123) — spreading miners is worse

**Key finding**: Game uses L2 distance (`dr²+dc²≤r²`) for alignment, while our policy uses Manhattan distance. The mismatch at `_JUNCTION_ALIGN_DISTANCE = 20` (Manhattan) vs game's 15 (L2) is actually a beneficial over-approximation — tightening it hurts performance.

**Conclusion**: v4 is at a robust local optimum. All 25+ variants tested across sessions 2 and 3 are identical or worse. The remaining optimization space is likely in:
1. Closing the offline-online gap (biggest opportunity)
2. Fundamentally different strategies (RL training, adaptive behavior)
3. Online-specific tuning (handling variable agent counts, opponent types)
