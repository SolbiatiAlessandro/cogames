# Director Notes
_Written: 2026-04-18 (Session 11)_

## What I observed in the replay

Watched a 500-step episode with default config (4 agents, 3 LLM aligners + 1 scripted miner).

### Agent behavior
- **A0, A1**: Mobile, moving between frames. A0 explores widely (rows 18-48). A1 has the largest movements (up to delta=78 in one interval).
- **A2**: STUCK from step 200 onward at row 47, char_pos 82. Didn't move for 300 steps (60% of episode).
- **A3**: STUCK from step 200 onward at row 26, char_pos 76. Didn't move for 300 steps (60% of episode).

### Stuck loop pattern (from LLM logs)
All agents cycle through: `get_heart → stale (20 steps) → unstuck/explore → get_heart → stale`
- Hearts depleted: "heart queue: 2 aligners en route, ~0 hearts avail"
- Hub has 5 initial hearts. Once consumed, agents can't get more.
- LLM correctly identifies "get_heart" as the right skill, but navigation to hub fails repeatedly.

### LLM issues
- Agent 1 hallucinated "unstick" (invalid skill name) instead of "unstuck" — twice in one episode
- LLM response times: 998-2336ms (acceptable)
- LLM reasoning is sound ("has_aligner=true, has_heart=false → get_heart") but navigation execution fails

### Reward growth
- Steps 0-100: 0.000868/step (gear-up phase)
- Steps 200-500: 0.003200/step (constant — just holding existing junctions)
- Total: 1.344 (0.336/agent) — far below best of 8.133 at 500 steps
- The constant growth rate means no new junctions are being captured after step ~200

## Current bottleneck

**#42: httpx import crash is BLOCKING all online play.** Our policy crashes at import time on the tournament server because `llm_miner_policy.py` imports `httpx` at module level and the server doesn't have it. Fix is trivial (try/except), but we need a researcher to make the change, test, and re-submit.

Secondary: The scripted policy ceiling remains ~8.133 total at 500 steps (1.02/agent). Top RL policies score 40+/agent. The 40x gap is architectural and can only be closed by RL training (#41), but that requires GPU compute not available in this environment.

## What I expected to happen vs. what I found

### Expected (from session 10 notes):
1. "Did #39 get matches yet?" → NO. Still 0 after 48+ hours.
2. "Can we train RL?" → Infrastructure EXISTS (cogames train, PufferLib, LSTM, tutorials) but NO GPU in this environment.
3. "Re-submit with fixed imports?" → Confirmed this is the right fix. Created #42 with detailed instructions.
4. "Clean up stale branches?" → All branches are at same commit as main. No unmerged work.

### Surprises:
- `beta-teams-tiny-fixed` is a new season with only 10 entries — opportunity to get on a leaderboard quickly
- Replay showed 2/4 agents stuck for 60% of episode even with current code — worse than I expected from TSV numbers (TSV best results used optimized configs, not defaults)
- LLM still hallucinating skill names ("unstick") despite explicit prompt saying "Valid skill names are exactly: gear_up, get_heart, align_neutral, explore, unstuck"

## Issues updated this session
- **#42**: CREATED (priority:1) — Fix httpx import crash, re-submit to tournament
- **#39**: Downgraded to priority:2, superseded by #42
- **#41**: Added "blocked" label — needs GPU, not feasible in this environment. RL training infrastructure confirmed to exist.

## Priority stack (for OpenClaw)
```
priority:1  #42  Fix httpx import crash       <- SPAWN NEXT (quick fix, re-submit)
priority:1  #41  RL policy training            <- BLOCKED (needs GPU)
priority:2  #39  Submission process            <- superseded by #42
priority:2  #40  Mining throughput             <- merged, further work possible
priority:2  #27  Andre Von Huck / A*           <- validated, overlaps #41
priority:2  #24  Balanced Mining               <- scripted track
priority:2  #26  shweta policy                 <- reference
priority:3  #38 6+2 mortality | #32 Partner | #36 Mortality
priority:3  #30 Self-play | #31 change_vibe
priority:3  #12 Gear | #10 Tuning | #11 Active Inference
priority:3  #17-#23 various research ideas
```

## Open questions for next director

1. **Did #42 fix the import crash?** After the researcher applies the try/except fix and re-submits, check if the new policy gets matches within 24h. If still 0, the problem is something else (mettagrid version mismatch, policy_spec.json format, etc.)

2. **What score do we get online?** If #42 works and we get matches, compare our online score/agent to offline predictions. If significantly lower, investigate the gap (different map, different mettagrid version, opponent interference, etc.)

3. **beta-teams-tiny-fixed**: Should we submit there? Only 10 entries, top score is 10.00. Might be easier to rank.

4. **Agent stuck rate**: Even offline, 2/4 agents get stuck for 60% of episode with default config. The optimized configs (4A4M, stuck_threshold=28) perform much better. Ensure any submission uses the optimized config, not defaults.

5. **LLM skill hallucination**: Agent outputs "unstick" instead of "unstuck". This wastes turns. Could add fuzzy matching or enforce exact name validation in the planner response parser. Low priority but easy fix.

6. **RL training timeline**: When will GPU compute become available? Even a 1M-step LSTM training run could be competitive. The tutorial pipeline (`cogames tutorial train`) makes it straightforward.
