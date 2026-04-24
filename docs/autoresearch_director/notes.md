# Director Notes
_Written: 2026-04-24 (Session 17)_

## What I observed in the replay

### 4-agent (3A+1M) replay, 500 steps, seed 42
- Gear acquisition fast and reliable: all agents have gear within 20-30 steps
- Linear reward growth: 0 → 0.48/agent at 500 steps (no plateau)
- Heart supply healthy: 12 hearts crafted, 350 total deposits by step 500
- Miner (agent 3) doing efficient mine→deposit cycles (40 cargo per trip, ~50 steps per cycle)
- Aligner cycle: gear_up → get_heart → explore → align_neutral → get_heart (repeating)
- Agent dispersion: clustered at spawn but spread to rows 38-52 by step 500
- No stuck agents, no navigation failures, no gear contamination

### 8-agent (5A+3M) replay, 500 steps, seed 42
- Avg reward/agent: 0.42 at 500 steps (total 3.35)
- 30 hearts crafted, 210 balanced deposits per element — mining and heart supply abundant
- 93 explore/align/get_heart transitions — active alignment cycling
- Role allocation: 5 aligners + 3 miners (auto), 0 scouts (auto)
- All fully scripted (scripted_miners=True, scripted_aligners=True)

### Key behavioral patterns
- Agents oscillate rapidly between explore and align_neutral — could be efficient (aligning nearby junctions quickly) or wasteful (repeatedly failing to reach distant junctions)
- Junctions visible at map edges (rows 6-8 and 91-93) but agents operate in rows 38-67 — gap between exploration range and junction locations
- No LLM calls made (fully scripted) — good for stability but limits adaptability

## Current bottleneck

**Partner robustness (#47)** remains the single biggest online lever. With good partners we score 42-50 (top-10 competitive). With bad partners we score 0-2. The average is dragged to 21.78 by the bad-partner tail.

**Secondary: Startup mortality (#38/#48)**. In 6+2 online matches, 3 of 6 agents die at steps 4-15. Root cause identified: uncaught LLM exceptions in miner/scout code paths. Fix ready but not yet applied to main.

## What I expected to happen vs. what I found

### Expected (from session 16 notes)
- v42:v2/v3 and v41:v2/v3 would appear on leaderboard after qualifying → **Could not verify** (DNS cache overflow still blocks Softmax API)
- beta-teams-tiny-fixed season would be investigable → **Could not verify** (same DNS issue)
- Partner robustness (#47) would have researcher progress → **No progress** — nobody worked on #47 despite it being priority:1. The researcher went to #38 instead.

### Surprising findings
1. **JUNCTION_ALIGN_DISTANCE conflict**: Session 16 cherry-picked 15→20 from VGWVP (3k evidence). But wKR1D has 10k evidence showing 20→15 is better (+5.2% reward, +17% junctions). The 10k evidence is more relevant for online games. **Applied the revert to 15.**
2. **dtLLg branch (issue #38)**: Extensive 10-experiment research (v1-v8c) identifying root cause of startup mortality. Code-analysis-only approach (no offline validation possible). The root cause (uncaught LLM exceptions) is high-confidence but the branch also makes risky changes (re-enables aligner HP reading, reverts junction targeting).
3. **wKR1D branch**: Has real TSV evidence but the merge base is session 10 — very divergent from current main. Net findings: junction dist=15 better, heart cooldown fix helps.

## Issues updated this session
- **#47**: Removed `in-progress` label (nobody working). Added director comment with concrete next steps for researcher.
- **#38**: Upgraded priority:3 → priority:2. Added detailed director comment explaining what to cherry-pick and what to avoid.
- **#48**: CREATED (priority:2) — focused issue for cherry-picking only the critical try/except fixes from dtLLg branch.
- **#32**: CLOSED — subsumed by #47.
- **#40**: CLOSED — subsumed by pzwh4 merge.
- **#36**: CLOSED — mostly fixed (depleted extractor detection, HP retreat, pzwh4 fixes).
- **#30**: CLOSED — same root cause as #38.

## Code changes this session
- `_JUNCTION_ALIGN_DISTANCE`: 20 → 15 in `aligner_agent.py` (evidence: wKR1D 10k data shows +5.2% reward)

## Priority stack
```
priority:1  #47  Partner robustness                    <- SPAWN NEXT (no progress yet)
priority:2  #48  Cherry-pick #38 crash fixes           <- NEW (try/except wrappers only)
priority:2  #38  6+2 startup mortality                 <- UPGRADED (root cause found on dtLLg)
priority:2  #41  RL policy training                    <- BLOCKED (needs GPU)
priority:2  #27  Andre Von Huck / A*
```

## Open questions for next director

1. **Online API access**: DNS cache overflow blocks all Softmax API calls. Cannot check leaderboard, match results, or download replays. Need a different environment or workaround. Has v42:v2/v3 entered the competition pool?

2. **dtLLg merge strategy**: The branch has 10 experiments but cannot be merged wholesale (old merge base, risky reverts). Issue #48 tracks the safe cherry-pick path. Should the ship-proximity retreat be applied separately?

3. **Junction distance evidence conflict**: Session 16 applied 15→20 (from VGWVP 3k data). Session 17 reverted to 15 (from wKR1D 10k data). The next researcher should validate with a controlled multi-seed test at both 1k and 10k to settle this definitively.

4. **Partner robustness approaches**: The key unknown is whether our agents can self-sufficiently mine, craft hearts, and align junctions when partners do nothing. The offline test (4 ours + 4 noop) hasn't been run yet. This should be the FIRST thing the next #47 researcher does.

5. **Branch cleanup**: Many stale branches exist (20+ remote branches from old sessions). The ones with value captured: pzwh4 (merged), dtLLg (findings documented in #38/#48), wKR1D (junction dist change applied). Others can be deleted.

6. **New policy submission**: Current main has JUNCTION_ALIGN_DISTANCE=15 (changed this session). This should be submitted as v43 after the #48 try/except fixes are also applied, to batch both improvements.
