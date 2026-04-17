# Director Notes
_Written: 2026-04-17 (Session 10, offline-to-online)_

## What I observed

### Online tournament state — DRAMATICALLY CHANGED
- **Season beta-cvc v8**: restructured. Only **51 entries** (was 405 in session 9).
- **Top-1**: `Gryffindor:v11` at **40.82/agent** (was `dinky:v27` at 27.31).
- **NONE of our 25 policies appear on the leaderboard.** All old entries gone.
- **Both partners now get the SAME score** — pure cooperative team scoring.
- `lessandro-scripted-v21:v1` uploaded April 16 at 17:29 UTC, has **0 qualifying matches in 24h**.
- Tournament IS active: Gryffindor, Slytherin, Ravenclaw, Softy, shweta policies all getting matches today.

### CRITICAL STRATEGIC DISCOVERY: Top policies are pure RL

Analyzed replay of Slytherin:v18 + Gryffindor:v18 match (score 52.2/agent):

**Action distribution (all 8 agents combined):**
- move_south: 11,579 | move_north: 11,305 | move_west: 8,000 | move_east: 7,727
- noop: 130
- change_vibe_*: **ZERO**

**Game stats:**
- 224 junctions gained (us: 7-8) = **30x gap**
- 19,084 total element deposits (us: ~640 at 3k) = **~10x gap** (adjusted for steps)
- 522,354 junction held steps
- Only 5 hearts withdrawn (same as us — hearts are NOT the bottleneck!)
- Agent survival: 3,500-9,900 steps (agents DO die, but still score 52.2/agent)

**What this means:** Top policies use ONLY movement actions. No gear specialization, no LLM calls, no skill system. They are trained RL neural networks that have learned efficient navigation, junction capture, and implicit coordination through millions of training steps.

### Branch reviews and merges
1. **`claude/amazing-meitner-JWXo2`** (issue #39): MERGED. Submission scripts + docs. `lessandro-scripted-v21:v1` was uploaded successfully but has 0 matches.
2. **`claude/amazing-meitner-pQoW5`** (issue #40): MERGED. Mining stuck fix (+55% reward at 3000 steps). Fixes: deposit timeout recognition, faster stuck threshold, stale blocked cells clearing, miner HP retreat, disabled aligner HP retreat.

### Previous session questions answered

1. **Did #39 submit successfully?** YES — `lessandro-scripted-v21:v1` uploaded April 16. But 0 qualifying matches in 24h.
2. **6+2 survival after MGrvP?** UNKNOWN — can't test online because no matches.
3. **3000-step HP decay?** Issue #40 found all agents die by ~3000 steps. Mining stuck fix improved reward from 1.02 to 1.59 at 3k steps, but agents still die.
4. **"Just use A* and hash tables" (#27)?** VALIDATED. Top policies use pure movement. Andre Von Huck was right.
5. **Clean up old branches?** Merged 2 branches (JWXo2, pQoW5). 30+ old remote branches remain.

## Offline-to-Online Gap Analysis

1. **Offline best**: 8.133 total (1.02/agent) at 500 steps, 8-agent. 1.59 total at 3000 steps with mining fix.
2. **Online rank**: UNKNOWN — 0 matches played. Previous entries removed from leaderboard.
3. **Gap is FUNDAMENTALLY architectural**, not just tuning:
   - Our scripted policy: complex skill system (gear_up, align_neutral, get_heart, mine, explore, unstuck)
   - Top RL policies: just move north/south/east/west
   - Junction capture rate: 7-8 vs 224 = 30x gap
   - This gap cannot be closed by improving the scripted policy incrementally

4. **Hearts are NOT the bottleneck** — correcting session 9's analysis. Top policies only withdraw 5 hearts (same as us). The score comes from junction held time, not hearts.

5. **Previous gap estimates were wrong:**
   - Mining: 28x gap → actually ~10x (adjusted for steps, new data shows top deposits ~19k not 14k)
   - Hearts: 33x gap → actually 1x (both us and top use exactly 5 from hub)
   - Junction captures: was not tracked → revealed as 30x = THE key gap

## Current bottleneck

**TWO parallel bottlenecks:**

1. **Submission pipeline broken** (#39): Policy uploaded but 0 qualifying matches. Possible causes:
   - `httpx` import at module level in `llm_miner_policy.py` — may crash on server
   - Queue congestion
   - Season v8 enrollment issue

2. **Fundamental approach gap** (#41): Our scripted/LLM policy ceiling is ~5-10 score/agent. Top RL policies achieve 40+/agent. Training an RL policy is the highest-leverage path.

## Issues updated this session
- **#39**: Comment with 0-match analysis. Labels unchanged (priority:1).
- **#40**: Comment with merge + strategic context. Branch merged. Mining is ~10x gap, not 28x.
- **#41**: CREATED (priority:1) — RL policy training. Highest leverage for online score.
- **#27**: Comment — Andre Von Huck's A*/hash-table advice validated by replay analysis.
- **#21**: Label updated to priority:3.

## Priority stack
```
priority:1  #41  RL policy training  <- HIGHEST LEVERAGE (30x junction gap)
priority:1  #39  Fix submission      <- BLOCKING (0 matches in 24h)
priority:2  #40  Mining throughput   <- merged +55%, scripted track
priority:2  #27  Andre Von Huck / A* <- validated, overlaps #41
priority:2  #24  Balanced Mining     <- scripted track
priority:2  #26  shweta policy       <- reference
priority:3  #38  6+2 mortality (merged) | #32 Partner robustness
priority:3  #36 Mortality | #30 Self-play | #31 change_vibe
priority:3  #12 Gear | #10 Tuning | #11 Active Inference
priority:3  #17 Skill Validation | #19 LLM Code Gen | #20 Spatial Part.
priority:3  #21-23 Meta/Social/Intrinsic
```

## Open questions for next director

1. **Did #39 get matches yet?** Check the API for `lessandro-scripted-v21:v1` match count. If still 0 after 48h, the policy is likely crashing server-side. Fix: wrap `httpx` import in try/except, or remove LLM dependency entirely for scripted mode.

2. **Can we train an RL policy (#41)?** Check if `cogames train` works in this environment. The existing tutorials and `pufferlib_policy.py` template should provide a starting point. Even a baseline RL policy trained for 1M steps might score higher than our scripted approach.

3. **Re-submit with fixed imports?** If #39 is stuck due to import crash, create a minimal policy bundle that:
   - Does NOT import `httpx` at module level
   - Uses only the scripted fallback (no LLM planner needed for 8-agent matches)
   - Has zero external dependencies beyond what cogames provides

4. **Hearts are NOT the bottleneck** — this invalidates several session 7-9 conclusions. The 5 hearts come from the hub's initial supply. No policy (including top-1) crafts additional hearts. The entire make_heart / mining-for-hearts strategy is irrelevant to scoring. What matters is: junction capture speed and junction hold time.

5. **What makes top RL policies capture 224 junctions?** Possible factors:
   - Efficient A* pathfinding (no BFS stuck loops)
   - Aggressive junction claiming (immediate alignment on contact)
   - Recapture speed (quickly taking back lost junctions)
   - Implicit multi-agent coordination (agents spread out to cover more junctions)
   - Zero time spent on gear management, LLM waits, or role assignment

6. **Clean up stale branches** — 30+ remote branches. After confirming session 10 deliverables pushed, delete merged branches: amazing-meitner-JWXo2, amazing-meitner-pQoW5.
