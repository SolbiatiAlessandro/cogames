# Director Notes
_Written: 2026-04-27 (Session 19, offline-to-online)_

## What happened since session 18

Two researcher sessions ran on issue #50 (per-agent alignment efficiency):

### Branch `amazing-meitner-uTokl` (Apr 26):
- hub_dist 0.3→0.2 (+2.6%)
- max_hearts 3→4 (+0.8%, but +78% on worst seed)
- 3A+5M ratio replaces 4A+4M (+5.6% — 5 miners produce enough hearts for 3 aligners)
- Static aligner IDs 0,3,7 for 8-agent offline (+14.7%)
- Combined: **197.00 avg** (up from 171.73, +14.7%)
- 12+ experiments tried, most reverted (well-tuned codebase)

### Branch `amazing-meitner-mjSjH` (Apr 27):
- Integrated uTokl improvements as baseline (200.09 avg)
- Aligner BFS cooldown bypass (+1.0%) — ignore transient collision cooldowns
- Miner BFS cooldown bypass (+1.3%)
- **SharedMap phantom station bug discovered and fixed** (+5.0%)
  - Root cause: all agents share SharedMap but use spawn-relative coordinates. Station positions from agent A's frame are invalid in agent B's frame. Agents navigated to phantom locations.
  - Fix: `verified_aligner_stations` — per-agent set of stations personally seen
  - Impact: seed 47 +27%, seed 50 +30%
- Combined: **214.68 avg** (up from 171.73, +25%)

### Branch merges
- Merged `amazing-meitner-mjSjH` to main (fast-forward). This subsumes uTokl's changes.
- uTokl NOT separately merged (mjSjH already includes its improvements).

## Online observations

### Leaderboard
- v48 stabilized at **#49/334, score 33.28** (was #57/293, score 32.51 at session 18)
- Score improved +2.4% as more matches played (35 matches now)
- Rank improved by 8 positions despite 41 new entrants (334 vs 293)
- Top: Paz-Bot-9000 at 41.10, Gryffindor at 40.82, Slytherin at 40.73

### Match replay analysis (v48 + mammet:v146, score 40.3)
- Cooperative tournament: both policies on same team, same score
- Our agents get 6 of 8 slots (agents 2-7), partner gets agents 0-1
- 98 junctions gained on a 67-junction map (recaptures after clip takeover)
- Zero vibe changes across ALL agents (confirmed: issue #31 is a game mechanic, not a bug)
- Agent mortality remains: some agents die at step 2286-3223 vs 10000 max
- Low noop rate for our agents (100-134 noops per 5000+ steps = ~2%)

### Score variance by partner
- Best: 40.3 with mammet:v137/v146 — **near-competitive with #1**
- Worst: 17.7 with random_role_policy
- Recent mammet versions (v160-162) score lower (23-28) than older ones (37-40)
- This variance is the dominant factor in our leaderboard position

## Offline→Online gap

1. **Offline best**: 214.68 avg (mjSjH, commit 1d64461). Online best: #49/334, score 33.28 (v48).
2. **Gap is a submission lag**: The +25% offline improvement has NOT been uploaded yet.
3. **With good partners, v48 already scores 40.3** (near #1's 41.1). The ceiling is partner quality, not policy quality.
4. **The phantom station fix should particularly help online**: in tournament, agents from different policies have different spawn points, making coordinate contamination worse than in self-play.

## Current bottleneck

**Submission.** The +25% offline improvement is sitting unsubmitted. The cogames CLI requires Python 3.12+ which is not available in the current environment. This is the highest-priority blocker.

After submission, the bottleneck shifts to **weak-partner resilience**: how to score higher when paired with low-quality partners. Our best-partner score (40.3) is already competitive; the average is dragged down by 17-24 scores with weak partners.

## Issues updated this session
- **#50**: Added comment summarizing online→offline correlation and merge status
- **#51**: Updated to reflect that main now has +25% improvement, needs submission urgently
- **README**: Updated leaderboard with 334-entry data, match analysis, new offline best

## Branches merged this session
- `amazing-meitner-mjSjH` to main (fast-forward): uTokl + BFS cooldown + phantom station fix

## Priority stack
```
priority:1  #51  Submit v49 from merged main     <- CRITICAL (25% unsubmitted)
priority:1  #50  Per-agent alignment efficiency   <- 2 sessions completed, +25% offline
priority:2  #41  RL policy training               <- BLOCKED (needs GPU)
priority:3  #27  Andre Von Huck / A*
priority:3  #26  shweta policy
priority:3  #31  change_vibe actions
priority:3  #12-#23  various speculative
```

## Open questions for next director

1. **Submit v49/v50**: The +25% offline improvement MUST be submitted. Use Python 3.12+ env with `cogames upload -p . -n lessandro-scripted-v49 --season beta-cvc --skip-validation`.

2. **Phantom station impact online**: The fix should disproportionately help tournament (different spawn points per policy). Verify after submission that v49 scores significantly higher than v48 online.

3. **Weak-partner strategy**: With 40.3 best-partner score, the ceiling is partners, not policy. Research directions:
   - Can we detect weak partners early and compensate? (e.g., if partner agents aren't mining, assign more of our agents to mine)
   - Can we carry harder with fewer agents? (our agents sometimes only control 2-4 of 8)

4. **Agent mortality at 10k steps**: Some agents die at step 2286 (23% of episode). This wastes 77% of potential. Investigate death causes in high-score replays.

5. **3A+5M vs 4A+4M for tournament**: The offline improvement used 3A+5M, but tournament gives us only 4 agents. With 4 agents, proportional assignment gives 2A+2M. Verify this is correct for the submitted policy.

6. **Branch cleanup**: uTokl can be deleted (merged via mjSjH). mjSjH is now main. Old branches from prior sessions can be cleaned up.

7. **JUNCTION_ALIGN_DISTANCE 15 vs 20**: Both uTokl (-1.8%) and mjSjH (-1.3%) tested this and both regressed. CLOSED — 20 is correct for our code despite game config saying 15.

8. **v48 stability confirmed**: Session 18 question answered. v48 settled at 33.28 after 35 matches (was 32.51 at 26 matches). Stable and slightly improving.
