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

**2026-05-12T05:24Z**: starting to run baseline. Config: 3A5M, stuck_threshold=28, 3000 steps.
- Seed 42: reward=127.71, 48 junctions
- Seed 43: reward=136.36, 55 junctions
- Seed 44: reward=138.99, 61 junctions
- **3-seed avg: 134.35** (baseline)

**2026-05-12T05:28Z**: Exp1 — Network-expansion priority targeting. Added bonus for junctions that unlock unalignable neighbors. Result: seed 42 WORSE (118 vs 128), seeds 43/44 unchanged. **DISCARDED.** Expansion bonus makes agents travel too far to frontier junctions.

**2026-05-12T05:38Z**: Exp2 — Multi-heart accumulation (raise threshold 3→5). Result: identical to baseline on all seeds. The `no_progress_on_target_steps` timeout fires before agents can accumulate hearts because the progress tracking is broken.

**2026-05-12T05:45Z**: Exp3 — Aligner count sweep (2A, 4A, 5A, 6A at 3000 steps seed 42). Results: 2A=116.45, 3A=127.71 (baseline), 4A=133.80, 5A=128.60, 6A=93.49. 4A is best single-seed but inconsistent across seeds.

**2026-05-12T05:57Z**: Exp4 — **Fix heart progress tracking bug.** Found that `state.last_has_heart` was updated BEFORE the `made_progress` check, so heart acquisition NEVER counted as progress. Fixed by saving previous values before update. Combined with raised heart accumulation (3→5) and stale timeout (3→8).
- Seed 42: 130.74 (+2.4%)
- Seed 43: 140.47 (+3.0%)
- Seed 44: 151.04 (+8.7%)
- **3-seed avg: 140.75 (+4.8% over baseline). KEPT.**

**2026-05-12T06:20Z**: Exp5 — **Aligner spread bonus.** Added bonus to junction targeting that prefers junctions far from other aligners' positions, encouraging map coverage spread. Weight=0.3 best after sweep (0.1, 0.3, 0.5, 0.8).
- Seed 42: 139.06 (+6.4% over heart-fix)
- Seed 43: 140.33 (same)
- Seed 44: 153.00 (+1.3%)
- **3-seed avg: 144.13 (+7.3% over baseline). KEPT.**

**2026-05-12T06:40Z**: Exp6 — Round-trip cost targeting. Changed scoring from `travel + hub_dist * 0.2` to `travel + hub_dist`. Result: avg 139.10, WORSE. Hub proximity bonus is important for keeping agents in a tight operating radius. **DISCARDED.**

**2026-05-12T06:48Z**: Exp7 — Dynamic hub weight based on heart count. Set hub_weight=0 when agent has >1 heart. Result: avg 139.45, WORSE. Multi-heart agents that chase distant junctions take too long to return to hub. **DISCARDED.**

**2026-05-12T06:54Z**: Exp8 — Fix JUNCTION_ALIGN_DISTANCE from 25 to 15 (game config value). Result: avg 141.53, WORSE. Actually the game's ClosureQuery uses `max(JUNCTION_ALIGN_DISTANCE, HUB_ALIGN_DISTANCE) = 25`, so 25 is correct. **DISCARDED.**

**2026-05-12T07:00Z**: Running 6-seed validation of best config (heart-fix + spread bonus).
