# autoresearch: issue #71 — Junction control efficiency (74% -> 80%+)

Branch: `autoresearch/issue-71-junction-control-efficiency`
Target issue: [#71](https://github.com/SolbiatiAlessandro/cogames/issues/71) — priority:1

## Plan

**2026-05-12 session start**: autoresearch starting, my plan is to improve junction control efficiency from ~74% to >80% of possible junction-time.

Issue #71 identifies the key gap to #1 (Softy:v103): our agents hold junctions 74% of possible time vs Softy's 84%. The ~10% gap maps directly to the ~6 point online score gap.

### Key levers to try:
1. **Junction targeting priority** — smarter scoring in `_cascade_priority_target()` (currently: `travel_dist + hub_dist * 0.2`)
2. **Multi-aligner coordination** — avoid two aligners targeting same junction; partition territory
3. **Hold vs expand tradeoff** — defend held junctions rather than always seeking new ones
4. **Faster initial claiming** — reduce time-to-first-junction-aligned
5. **Agent lifespan equalization** — prevent early deaths that reduce junction hold time

### Starting point:
- Best config from prior research: 3A5M, stuck_threshold=28, hazard-free BFS
- 6-seed avg at 1000 steps: ~4.83
- We'll baseline at 3000 steps to better capture junction holding behavior

## Log
