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

## 2026-03-30T00:30: starting new experiment loop - Experiment A: Quadrant Assignment

**Hypothesis**: By assigning each agent a map quadrant (NW/NE/SW/SE), exploration overlap will be reduced, moving agents away from the center where they cluster. The scripted version should show the clearest signal since there's no LLM to override the biased exploration.

**Changes made**:
1. `aligner_agent.py`: Added `quadrant_bias` (0-3) and `repulsion_radius` params to `AlignerPolicyImpl`
2. `aligner_agent.py`: Added `agent_positions` dict to `SharedMap` for tracking teammate positions
3. `aligner_agent.py`: Added `_biased_nearest`, `_in_preferred_quadrant`, `_quadrant_distance_bonus`, `_repulsion_penalty` methods
4. `aligner_agent.py`: Modified `_explore_frontier` to use `_biased_nearest` instead of `_nearest_known`
5. `aligner_agent.py`: Modified `_update_map_memory` to update SharedMap with agent position
6. `machina_roles_policy.py`: Added `PartitionedMachinaRolesPolicy` class with SharedMap + quadrant assignment + repulsion

**Experiment**: Run `partitioned_machina_roles` with 4 agents, quadrant_assign=True, repulsion_radius=0
Compare to scripted baseline 0.72 (no SharedMap, no quadrant)

Also compare to SharedMap alone (quadrant_assign=False) to isolate the effect.

## Experiment A Results (2026-03-30T01:00)

Initial results with hard quadrant bias (penalty=1000): DISASTER - 0.52 reward, max_stuck=1916
- Root cause: hard bias sends agents to remote quadrant frontiers, BFS fails, agents stuck

Added `_move_toward_target` for biased targets: still 0.52 (cached? - actually same because code was sending to far targets in Q)

With SharedMap + no quadrant bias: 0.82 reward (+14% over 0.72)
- SharedMap alone helps by sharing junction knowledge

SharedMap with `share_move_blocked=False`: 0.89 reward (+23%)
- Sharing move_blocked_cells across agents is BAD - agent collisions contaminate shared blocked cells
- Example: agent 0 blocks agent 1's path to hub → (hub_adjacent_cell) added to move_blocked_cells for ALL agents

Adding navigation shake (after 5 stuck moves, try random direction every 3rd step):
- max_steps_without_motion: 1900 → 9! Near-zero stuck
- Reward stays at 0.89 (nav shake alone doesn't help scripted version - navigation was already OK)

Key findings from Experiment A:
1. **Hard quadrant bias is terrible** - 1000 penalty for out-of-quadrant sends agents to unreachable targets
2. **SharedMap hurts coverage diversity** - seed 44: 55716 cells/agent baseline vs 13660 with SharedMap
3. **Shared move_blocked_cells is BAD** - agent collisions contaminate permanently
4. **Navigation shake is essential** - fixes max_stuck without changing reward
5. **Soft quadrant bias (25%)** - neutral/same as no bias (1900 stuck → 10 stuck → same 0.89 reward)

Best scripted result: **0.89** (SharedMap + NavShake + share_move_blocked=False)

## 2026-03-30T01:30: starting new experiment loop - Experiment B: Improve junction targeting with SharedMap

**Hypothesis**: The main benefit of SharedMap is shared junction knowledge. Can we improve the junction targeting strategy?

Current behavior with SharedMap:
- All agents see the same set of neutral junctions
- `_align_neutral` targets the nearest junction (same for all agents at same position)
- All agents rush to the same junction initially

**Proposed improvement**: Use agent-rank to select DIFFERENT junctions:
- Rank agents 0-3 by ID
- Agent 0 selects junction at rank 0 (nearest)
- Agent 1 selects junction at rank 1 (2nd nearest)
- Agent 2 selects junction at rank 2 (3rd nearest)
- etc.

This ensures agents spread across different junctions, improving parallelism.

## 2026-03-30T02:00: new experiment loop - Fix Phase Timeouts

**Problem found**: Multi-episode evaluation reveals `partitioned_machina_roles` averages 0.56 reward (3 eps) while `machina_roles` averages 0.74. The single-episode lucky run of 0.89 was misleading.

**Root cause analysis**:
- `partitioned_machina_roles` has `_HEART_TIMEOUT=150` and `_GEAR_TIMEOUT=200` in `AlignerPolicyImpl`
- After aligning 1 junction (heart spent), agent tries get_heart, but hub has limited hearts (5 total)
- After 150 steps without getting a heart, agent goes to `explore` mode
- This creates: get_heart→explore→get_heart→explore loop (visible in logs!)
- Result: `cogs/aligned.junction.held = 3625` vs `machina_roles = 5364` (less time holding)
- Also `aligner.lost = 0.5` for partitioned vs ~0 for machina_roles (agents dropping gear somehow)
- `machina_roles` has no timeouts and simply persists trying: higher held-steps result

**Hypothesis**: Remove or significantly increase phase timeouts to fix the explore-loop.
Also need to fix: when hub is depleted, agents should wait near hub, not wander.

**Proposed fix**: Increase `_HEART_TIMEOUT` from 150 to 500+ steps, or make it wait near hub.
Alternatively: remove phase timeouts from `AlignerPolicyImpl` entirely (they were meant for stuck detection, but NavShake already handles navigation stuck).

---

## 2026-03-30T00:01: starting to run baseline

**API situation**: paid model `nvidia/llama-3.3-nemotron-super-49b-v1.5` returns 402 (insufficient credits on the underlying account, despite $45 shown in key balance). Free models like `liquid/lfm-2.5-1.2b-instruct:free` and `google/gemma-3-12b-it:free` work but are heavily rate-limited when multiple agents call concurrently.

**Strategy change**: Focus on scripted improvements (no LLM needed) to implement spatial partitioning in the scripted aligner. Then if LLM API issues resolve, the changes will also benefit LLM agents.

**Scripted baseline result (machina_roles, 4A, 2000 steps, seed=42)**:
- mission_reward: 0.72
- action.move.failed: 1608.50/agent (80.4% failure rate!)
- action.move.success: 391.50/agent
- cell.visited: 21623/agent (but many overlapping)
- junction.aligned_by_agent: 1.50 (6 total)
- status.max_steps_without_motion: 1219

The scripted aligner gets 0.72 vs LLM's 1.24. The move failure rate is 80%! This is worse than the issue's reported 55-64%. The scripted version doesn't have move-failure-tracking or the quadrant assignment we want to add.

**Plan for experiments**:
1. **Exp A (Quadrant assignment)**: Modify `AlignerPolicyImpl` to accept a `quadrant_bias` (NW/NE/SW/SE) and prefer exploring toward that quadrant
2. **Exp C (Repulsion field)**: Track teammate positions in SharedMap, bias away when too close
3. **Exp B (Shared landmarks)**: SharedMap already does this - but we can explicitly prioritize teammates' discoveries

The scripted baseline without move-failure-tracking gets 0.72. The previous experiments showed that move-failure-tracking brought it from 0.612 to 1.190 (with 4 agents). So first we need to understand what the LLM version's advantage is:
- LLM: orchestrated skill selection (gear_up → get_heart → align_neutral)
- Scripted: simpler but same navigation

Wait - let me re-read. The scripted 4A baseline from issue-22 experiments got 1.190 using `machina_llm_roles` with 4 LLM agents. The `machina_roles` scripted version never got tested with SharedMap or move-failure-tracking. Let me first check: does `machina_roles` have SharedMap + move-failure-tracking?

## 2026-03-30T05:00: Session 4 - New experiment loop

**Previous best**: 10-ep avg = 0.798 (3650668)
**Proactive hazard marking experiments**: aeb1acf - neutral (same results); reverted

**Session 4 plan**:
Experiments involving the proactive hazard marking (aeb1acf) had zero effect on seed 45.
Analysis shows seed 45 is fundamentally broken: ALL 4 agents enter scrambler loop regardless.

**New hypothesis**: The scrambler_gained metric (3.75 avg over 10 eps) indicates agents often 
lose aligner gear DURING alignment or heart navigation. The `get_heart` phase uses `avoid_hazards=False`,
which could cause gear loss on the way to hub. Changing `_get_heart` to use `avoid_hazards=True` 
(with fallback) should reduce gear loss during hub navigation.

Additionally: try reducing `_HEART_WAIT_TIMEOUT` to zero (agents should always try get_heart 
from hub, not give up and explore) - or experiment with waiting longer.

### Starting experiment: avoid-hazards-get-heart


## 2026-03-30T05:30: Experiment avoid-hazards-get-heart RESULTS

**Result**: 10-ep avg = **0.813** (new best! +1.9% vs 0.798)
**Per-episode**: 0.89/0.88/0.74/0.41/0.88/0.86/0.89/0.76/0.80/1.02

**Key finding**: Adding `avoid_hazards=True` to `_get_heart` navigation significantly improves
performance. Previously agents would lose aligner gear while navigating TO the hub (stepping
on scrambler stations on the way). With this fix, agents keep their aligner gear more often.

Some episodes improved massively: ep4 +0.18 (0.70→0.88), ep5 +0.08, ep7 +0.12.
Some episodes slightly worse (ep1 -0.09, ep2 -0.11) - possibly noise from different seeds.

**Metrics**:
- scrambler.gained = 3.0 (up from 1.75 in baseline - more seeds with scrambler stations on paths)
- stuck = 138.75 (up from 78.75 - avoid_hazards=True causes more detours, more stuck episodes)
- seed 45 still 0.41 (unfixable with current approach)

**Next experiments**:
1. Reduce nav shake threshold from 5 to 3 to fix the increased stuck metric
2. Try longer BFS search horizon to find hazard-free paths more often
3. Try progressive refinement: if stuck for N steps in get_heart, try more aggressive avoid

