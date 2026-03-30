# Issue 20: Coordinated Multi-Agent Exploration via Spatial Partitioning

Branch: `autoresearch/issue-20-coordinated-multi-agent-spatial-partitioning`

## Issue Summary

**Hypothesis**: Agents currently explore independently, leading to massive overlap and congestion.
In replay analysis: 3 agents visiting 12k-27k cells each while clustering near center, vs 1 agent visiting 43k cells with 0.2% move failures.
Multi-agent move failure rates are 55-64% vs 0.2% single-agent.
By partitioning the map into exploration zones and sharing discovered landmarks, agents could achieve 3x the single-agent coverage instead of the current 0.5x.

**Issue-defined success criteria:**
- Total unique cells visited by team > 100k at 1000 steps (vs current ~50k with overlap)
- Per-agent move failure rate < 20% (vs current 55-64%)
- Junction discovery rate > 1 junction per 100 steps (vs current ~0.7)
- No two agents within 10 cells of each other for >50 consecutive steps

**Suggested experiments:**
- A: Quadrant assignment — assign each agent a map quadrant (NW/NE/SW/SE) and bias exploration toward their zone
- B: Shared landmark broadcasting — when any agent discovers a junction or hub, broadcast to all agents via SharedMap
- C: Repulsion field — add teammate positions to agent state; when within 15 cells of a teammate, bias movement away
- D: Sequential deployment — stagger agent starts

## Context from Previous Experiments

Best result so far: **1.240** reward with 4 aligners, 2000 steps, seed=42.
- `cogsguard_machina_1.basic`, `-c 4`, 2000 steps
- 6/7 junctions aligned (heart supply ceiling)
- max_steps_without_motion=11 (good nav)
- SharedMap already shared between all agents (all see same map)

Key insight from previous sessions:
- The bottleneck is NOT exploration/navigation — it's heart supply (5 hearts, so max 6 alignments)
- SharedMap already works (one Python object, shared by reference)
- 4A+0S at 2000 steps is the best config found

However, this issue is specifically about move failure rate and coverage efficiency.
The issue cites 55-64% move failure in multi-agent configs.
With our current 4A setup, max_stuck is only 11 (near zero).
So the move failure issue may have been largely addressed by move-failure-tracking.

**My plan**:
1. Run baseline with 4A, 2000 steps to confirm ~1.24 reward
2. Implement Experiment A: Quadrant assignment for aligners
   - Each aligner gets a different exploration bias (NW/NE/SW/SE quadrant)
   - When exploring, prefer frontier cells in their assigned quadrant
   - Should reduce collision and improve coverage efficiency
3. Implement Experiment C: Repulsion field (track teammate positions via SharedMap, bias away when too close)
4. Explore if we can beat the heart ceiling with better coordination

---

## 2026-03-30T00:00: autoresearch starting, my plan is to...

Implement spatial partitioning for aligner agents to reduce congestion and improve coverage.

The key insight from the issue is that agents cluster near center and block each other.
Our current best (1.24) uses 4 agents all starting at hub, all doing the same exploration pattern.

**Primary strategy**: Give each agent a "home quadrant" to prefer during exploration.
When an agent's explore skill fires, they should preferentially explore toward their assigned quadrant.
This should:
1. Reduce agents blocking each other (less overlap)
2. Improve junction discovery rate (cover more map area)
3. Potentially help discover the elusive 7th junction that's currently unreachable

The heart supply ceiling at 6/7 junctions might be breakable if:
- Agents discover junctions faster and align earlier → more held-steps
- Better coverage finds alternative paths to stuck junctions

**Secondary strategy**: Track teammate positions in SharedMap and add repulsion.
When an aligner is within 15 cells of a teammate, bias movement away.

I will run baseline first, then iteratively add features.

---

## 2026-03-30T00:01: starting to run baseline

Running: `uv run cogames run -m cogsguard_machina_1.basic -c 4 -p class=machina_llm_roles,kw.num_aligners=4 -e 1 -s 2000 --action-timeout-ms 10000 --seed 42`
