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
