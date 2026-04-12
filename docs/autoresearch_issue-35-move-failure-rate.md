# Autoresearch Issue 35: Move Failure Rate - Navigation Quality Crisis

Branch: `claude/amazing-meitner-ahBE5`

**Issue direction:** 53% of all move actions fail (5289 failures vs 4711 successes per agent in self-play). dinky achieves 98.5% move success. Fix navigation to reduce move failures, improve map coverage, and stop wasting action throughput on failed moves.

**Success criteria (from issue):**
- `action.move.failed` per agent <= 500 at 10k steps (currently 5289, target 10x improvement)
- `cell.unique_visited` per agent >= 1000 (currently 342)
- `cell.max_distance_from_spawn` >= 70 (currently 53.6)
- Move success rate >= 90% (currently 47%)

---

## 2026-04-12T11:00:00Z: autoresearch starting, my plan is to...

Starting issue #35. Root cause analysis from code review:

1. **Extractors are invisible obstacles**: BFS routes through extractor cells because they're not in blocked_cells until a move fails. The `move_blocked_cells` mechanism exists but extractors are only discovered reactively.
2. **Agent congestion in self-play**: 8 agents cluster near spawn. In coop matches (4.5% failure) this is much less of an issue since partner agents spread out.
3. **Greedy fallback is blind**: When BFS fails, `_greedy_move_toward_abs` and the greedy approach cell fallback pick directions purely by Manhattan distance, ignoring all terrain.
4. **Optimistic BFS has no congestion avoidance**: `_bfs_optimistic_direction` treats unknown cells as walkable but doesn't avoid cells near other agents.

**Plan:**
- Experiment 0: Run baseline (current code, 8-agent cross_role, 1000 steps) and measure move success metrics
- Experiment 1: Add agent position tracking to SharedMap, use it to avoid congestion in BFS
- Experiment 2: Improve greedy fallback to avoid known blocked cells
- Experiment 3: Add perpendicular retry on move failure instead of waiting for next planning cycle
- Experiment 4: Agent dispersion via quadrant-based explore targets

---

## 2026-04-12T11:30:00Z: starting to run baseline

Running: `cogames play -m cogsguard_machina_1 -c 8 -p "class=cross_role,kw.num_aligners=3,kw.llm_timeout_s=5" -s 1000 -r log --autostart`

**Baseline results:**
- Mission reward: 0.729/agent
- junction.held: 6291, junction.gained: 11, heart.withdrawn: 10
- Move success rate: 79.0% (6214 success / 1655 failed)
- Average failed/agent: 207 (projected ~2069 at 10k)
- Per-agent breakdown:
  - Agent 0 (aligner): 80.3% success (197 failed)
  - Agent 1 (miner): 67.4% success (326 failed)
  - Agent 2 (miner): 75.8% success (242 failed)
  - Agent 3 (miner): 95.5% success (45 failed)
  - Agent 4 (miner): 90.7% success (82 failed)
  - Agent 5 (miner): 73.0% success (266 failed)
  - Agent 6 (miner): 65.8% success (342 failed)
  - Agent 7 (miner): 84.5% success (155 failed)

Key observations:
- Huge variance between agents (4.5% to 34.2% failure rate)
- Miners have higher failure rates than aligners on average
- `_greedy_move_toward_abs` is completely blind (Manhattan only, ignores obstacles)
- Multiple skills fall back to greedy when BFS fails
- Navigation shake cycles directions blindly

**First experiment: Smart Greedy Fallback** - Make greedy navigation obstacle-aware by checking blocked_cells before choosing direction.

---
