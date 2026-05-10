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
