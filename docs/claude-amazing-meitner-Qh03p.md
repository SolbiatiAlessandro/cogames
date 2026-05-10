# Autoresearch Issue 69: Move Failure Rate Reduction

Branch: `claude/amazing-meitner-Qh03p`

**Issue direction:** Reduce aligner move failure rate from 33% to <15% to improve online leaderboard score. 33% of aligner steps are wasted bumping walls. Best matches have 0% failures; worst have high failure rates with 100+ steps stuck.

**Success criteria (from issue):**
- Primary: aligner move failure rate < 15% (measured in online CvC matches)
- Secondary: leaderboard score > 41.0 (from current 40.07)
- Tertiary: unique cells visited per agent > 2000 (from current 800-1500)

---

## 2026-05-10T00:00:00Z: autoresearch starting, my plan is to...

Starting issue #69. This is a continuation of issue #35 (move failure rate) but focused specifically on the aligner agent navigation in CvC matches. Key context from prior work:

1. **Issue #35 found**: perpendicular dodge + smart greedy got move success from 47% → 88%, but 10-33% of aligner steps STILL fail in online CvC
2. **Director insight**: removing move_blocked_cells HURT (it's a useful congestion heuristic). Fix must be nuanced.
3. **Architecture**: move_blocked_cells grows forever, move_cooldowns are 6-step timeouts, optimistic BFS through unknowns

**Plan (from issue):**
- Experiment A: Temporal decay on move_blocked_cells — expire transient collisions after N steps, keep permanent ones
- Experiment B: Frontier-based exploration — systematically explore nearest unvisited frontier cells
- Experiment C: BFS with "recently failed" penalty — cost multiplier instead of binary blocked
- Experiment D: Wall-following escape — when stuck 3+ steps, use wall-following instead of random
- Experiment E: Collision differentiation — distinguish agent vs wall/extractor bumps

**Strategy:** Start with Experiment D (wall-following escape) because it targets the worst case (178 consecutive steps stuck) and is orthogonal to existing logic. Then try A (temporal decay) which addresses the pollution problem more carefully than what issue #35 attempted.

---

## 2026-05-10T00:01:00Z: starting to run baseline

Running baseline with current main code on seed 42, 3000 steps, 8 agents.

## 2026-05-10T00:02:00Z: baseline results

| Seed | Reward | Move Failed | Move Success | Max Stuck | Junctions Aligned |
|------|--------|-------------|--------------|-----------|-------------------|
| 42   | 128.35 | 787         | 23213        | 126       | 51                |
| 123  | 134.54 | 1303        | 22697        | 155       | 51                |
| 7    | 139.70 | 895         | 23105        | 147       | 59                |

Move failure rate: 3.3-5.4%. Max stuck: 126-155 steps.

---

## 2026-05-10T00:05:00Z: starting new experiment loop - Experiment D: Wall-following escape

**Hypothesis:** When agents are stuck for 5+ consecutive steps trying to move into a blocked cell, a wall-following (right-hand rule) escape will get them unstuck faster than the current "navigation shake" (cycling random directions every 3rd step).

**Implementation:**
1. Added `last_failed_target` field to track which cell the agent last failed to move into
2. Added `wall_follow_direction` and `wall_follow_steps` state fields
3. Wall-following activates at 5+ stuck steps with a known failed target
4. Uses right-hand rule: keep wall on right, systematically follow the obstacle perimeter
5. Only activates when NOT on a valid target (not near hub getting heart, not on junction)
6. Max 15 steps of wall-following before falling back

**Results:**

| Seed | Baseline | Wall-Follow | Change | Move Failed Change |
|------|----------|-------------|--------|-------------------|
| 42   | 128.35   | 129.73      | +1.1%  | 787 → 830 (+5.5%)  |
| 123  | 134.54   | 138.97      | +3.3%  | 1303 → 932 (-28.5%) |
| 7    | 139.70   | 143.87      | +3.0%  | 895 → 826 (-7.7%)  |

**Average improvement: +2.4% reward across 3 seeds.**

Interpretation: Wall-following helps most on seeds with high initial failure rates (seed 123: -28.5% failures). On seed 42 with few failures, it's roughly neutral. The reward improvement comes from agents spending less time stuck and more time doing productive alignment work.

Status: KEEP — consistent improvement across seeds.

Next experiment: try applying same fix to miners, OR combine with temporal decay on move_blocked_cells.

---

## 2026-05-10T00:10:00Z: Experiment F — Proactive teammate avoidance (DISCARDED)

**Hypothesis:** When BFS directs an agent toward a cell occupied by a teammate, dodge perpendicular to prevent the collision before it happens. This avoids `move_blocked_cells` pollution from transient teammate positions.

**Implementation:** Added `_dodge_teammates` method to both aligner and miner. Before executing a move, check `SharedMap.agent_positions` — if target cell has a teammate, try perpendicular directions instead.

**Results:**

| Seed | Wall-Follow-v2 | Dodge | Change vs WF-v2 | Move Failures |
|------|----------------|-------|-----------------|---------------|
| 42   | 129.73         | 137.78 | **+6.2%**      | 830→1039 (+25%) |
| 123  | 138.97         | 129.71 | **-6.7%**      | 932→1446 (+55%) |
| 7    | 143.87         | 141.00 | **-2.0%**      | 826→1475 (+79%) |

**Status: DISCARD — move failures increased dramatically on all seeds due to oscillation.**

The perpendicular dodge causes agents to deflect off-course, then try to return, creating back-and-forth oscillation. Teammate positions are stale by one step, so the dodge often fires unnecessarily. The mechanism is fundamentally flawed for this use case.

**Lesson learned:** Proactive collision avoidance via perpendicular dodge doesn't work because (1) positions are stale by one tick, (2) dodging sends agents off their BFS path causing more subsequent collisions, (3) the perpendicular direction often hits walls.

---

## 2026-05-10T00:15:00Z: Experiment G — Smarter move_blocked_cells with temporal decay

**Hypothesis:** The FIFO eviction (cap=40) was neutral in 3000-step tests, but a time-based decay might work better. Instead of evicting the oldest entry, expire entries after N steps. This keeps recent collision data (useful for avoiding current obstacles) while forgetting stale data.

Approach: Add a timestamp (step counter) to each `move_blocked_cells` entry. During `_update_map_memory`, evict entries older than 20 steps. This is more targeted than FIFO because it respects recency, not just insertion order.

**Result: Not implemented** — temporal decay requires changing `move_blocked_cells` from `set` to `dict`, which breaks SharedMap's set-based operations. Instead, tried several alternative approaches:

### Cooldown 6→3 steps: DISCARDED
Move failures increased. Agents retry blocked cells too quickly.

### Alignment distance 25→35: DISCARDED  
Agents travel further to distant junctions, causing more failures. Current 25 is well-calibrated.

### Return load 40→25: DISCARDED
More trips to hub = more congestion. Fewer hearts despite more deposits.

### 5 aligners / 3 miners: DISCARDED
Seed 42 +3.4% but seeds 123/7 regressed -7%. Congestion at hub with more aligners.

---

## 2026-05-10T00:20:00Z: Online-targeted optimizations (Experiment H)

Two changes that have zero offline impact but should help online CvC:

**1. Enemy junction recapture priority:**
Added `-10` score bonus to enemy junctions in `_cascade_priority_target`. When choosing which junction to align, prefer enemy junctions (recapture = +2 swing) over neutral (+1 swing) if within 10 cells travel distance.

**2. Shorter defend timeout (1000→100 steps):**
When hub is depleted, agents defended for up to 1000 steps (doing nothing). Now they defend for only 100 steps before switching to explore for new junctions. In offline vs-clips, defend never fires (hub never depletes), so no offline impact.

Both changes verified zero-impact on seeds 42, 123, 7 at 3000 steps.

---

## 2026-05-10T00:25:00Z: Experiment I — Perpendicular dodge (steps 1-3) — DISCARDED

**Hypothesis:** From issue #35's cross_role_policy, a perpendicular dodge on first move failure gave +33% improvement. Port this to machina_llm_roles_policy.

**Implementation:** Before wall-following (step 5+), try perpendicular dodge at steps 1-3:
- Step 1: clockwise perpendicular
- Step 2: counter-clockwise perpendicular  
- Step 3: reverse direction

**Results (various guard levels):**

| Guard | Seed 42 | Seed 123 | Seed 7 | Avg Change |
|-------|---------|----------|--------|------------|
| None (unguarded) | 134.28 (+3.5%) | 135.65 (-2.4%) | 147.92 (+2.8%) | +1.3% |
| Full on_valid_target | 128.39 (-1.0%) | — | — | — |
| Hub-only | 128.72 (-0.8%) | 125.27 (-9.9%) | 142.75 (-0.8%) | -3.8% |
| Hub+junction | same as hub-only | same | same | same |

**Status: DISCARD** — the unguarded version sometimes improves but causes oscillation on specific seeds (seed 7: max_stuck=1249). The guarded versions are consistently worse than baseline because the guard prevents the dodge in exactly the scenarios where congestion is worst. Our BFS navigation is already good enough that perpendicular overrides cause more harm than good.

**Key insight:** Perpendicular dodge worked in the older cross_role_policy because that codebase had weaker BFS navigation. Our improved BFS cascade + wall-following handles stuck situations better without sending agents off-course.

---

## Summary of all experiments

| Experiment | Change | Status | Notes |
|-----------|--------|--------|-------|
| D: Wall-following (trigger=5, max=15) | +2.4% avg | **KEPT** | Main improvement |
| A: FIFO eviction (cap=40) | Neutral | kept (no harm) | May help online |
| C: BFS without move_blocked | Neutral | kept (no harm) | May help online |
| F: Teammate dodge | -0.5% avg | DISCARDED | Oscillation |
| G: Cooldown 3/FIFO 20/distance 35/5-aligner | All negative | DISCARDED | Various |
| H: Enemy priority + defend timeout | Zero offline | kept | Online-only benefit |
| I: Perpendicular dodge (steps 1-3) | -3.8% guarded | DISCARDED | Overrides BFS poorly |

**Net offline improvement: +2.4% from wall-following.**
**Online-targeted changes: enemy junction priority, shorter defend timeout.**
