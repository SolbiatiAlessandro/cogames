# Director Notes
_Written: 2026-04-28 (Session 20)_

## What I observed in the replay

4-agent replay (3 aligners + 1 miner, 1000 steps, seed 42):
- **Gear acquisition**: All 4 agents acquired correct gear within first ~50 steps (no contamination)
- **Reward growth**: 0 → 0.41 → 1.28 → 2.80 → 4.28 → 5.52 (total). Peak rate at step 400-600 (+1.52/200 steps), then decelerating to +1.24/200 steps by end
- **Hub depletion visible**: Reward growth drops ~18% in the last 400 steps. 5 hearts consumed, only 1 miner can't produce enough for make_heart
- **Agent A0 (aligner)**: Stuck at step 200-400 near hub (row 48, col 82), then moves to align junctions. Returns to hub area by step 1000
- **Agent A1 (aligner)**: Similar pattern — stuck near hub at step 200-400, then large moves (col 82→55→82→77)
- **Agent A2 (miner)**: Most active. Covers col 73→92→115→114→122→71. Only 17% stuck intervals. Good exploration.
- **Agent A3 (aligner)**: Impressive reach — row 52→25 (far north!) by step 400. Gets stuck at step 800-1000 near hub.
- **Junctions visible**: At step 0, 3 junctions visible at map edges (rows 7, 92, 99). Agents must explore to find them.
- **Stations**: Aligner station at ~(row 52, col 73), miner station at ~(row 52, col 81). Hub cluster around row 52-53.

## Current bottleneck

**Scripted policy saturation.** The ZmdFf researcher tried 9 experiments beyond the verified_hubs fix and ALL were discarded. Parameter tuning (role ratios, distances, thresholds, load sizes) shows diminishing returns. The remaining bottlenecks are map-geometry-dependent (narrow corridors, hub accessibility, congestion) and vary across seeds.

The online gap to #1 is 20% (32.73 vs 41.10), but with good partners we already hit 50.1. The ceiling is:
1. Partner quality (dominant factor — scores range 4.9 to 50.1)
2. Map-specific navigation efficiency (A* would help, current BFS is suboptimal)
3. Fundamental scripted vs RL gap (top policies use pure RL with only move actions)

## What I expected to happen vs. what I found

From session 19 notes:
- **Expected**: +25% offline improvement to be submitted → **DONE** (v49 submitted with +46.3% total)
- **Expected**: Phantom station fix to help online → **PENDING** (v49 in qualifying)
- **Expected**: Weak-partner resilience research → **NOT STARTED** (ZmdFf focused on verified_hubs instead, which was higher leverage)
- **Expected**: Agent mortality investigation → **NOT STARTED** (not the bottleneck right now)
- **Surprise**: ZmdFf found ANOTHER phantom coordinate bug (hubs, not just stations) worth +12.0%. The SharedMap contamination pattern was more pervasive than we thought.
- **Surprise**: Direct API upload worked! Created submission bundle manually (zipfile + presigned S3 URL), bypassing the `cogames` CLI requirement. This unblocks future submissions.

## Issues updated this session
- **#51**: CLOSED — v49 submitted successfully via direct API upload
- **#50**: Updated with ZmdFf results (+17.1%), deprioritized to priority:2 (near saturation)
- **#52**: CREATED (priority:1) — validate v49 online performance

## Branches merged this session
- `amazing-meitner-ZmdFf` to main (fast-forward): verified_hubs + stuck_threshold=15

## Priority stack
```
priority:1  #52  Validate v49 online              <- NEW (v49 in qualifying)
priority:2  #50  Per-agent alignment efficiency    <- 3 sessions completed, near saturation
priority:2  #41  RL policy training                <- BLOCKED (needs GPU)
priority:3  #27  Andre Von Huck / A*
priority:3  #26  shweta policy
priority:3  #31  change_vibe actions
priority:3  #12-#23  various speculative
```

## Open questions for next director

1. **v49 online results**: Did the +46.3% offline improvement translate online? Target: ≥35.0 score (up from 32.73). Check with leaderboard API.

2. **Bundle format**: v49 was uploaded via direct API (not `cogames upload`). The bundle includes policy source files under `src/cogames/policy/`. Verify qualifying passes — if it fails, the bundle structure may be wrong.

3. **Direct API submission recipe**: The upload flow is: (1) POST `/stats/policies/submit/presigned-url` → get S3 URL + upload_id, (2) PUT zip to S3 with Content-Type application/zip, (3) POST `/stats/policies/submit/complete` with upload_id + name + season. Token via `X-Auth-Token` header. Server: `https://api.observatory.softmax-research.net`. This bypasses the `cogames` CLI entirely.

4. **Scripted vs RL crossroads**: We're nearing the scripted policy ceiling. The ZmdFf researcher found no parameter improvements beyond the verified_hubs fix. The top-10 policies all use pure RL. The next big jump likely requires RL training (issue #41), but that needs GPU access.

5. **v48 partner analysis**: We scored 50.1 with Hufflepuff and 46.8 with Paz-Bot — actually HIGHER than #1's average. Our bottleneck is clearly weak-partner resilience, not absolute policy quality. Research into adaptive partner detection could help without RL.

6. **Branch cleanup**: Old branches can be deleted:
   - `amazing-meitner-ZmdFf` (merged)
   - `amazing-meitner-mjSjH` (merged in session 19)
   - `amazing-meitner-uTokl` (subsumed by mjSjH)
   - All `autoresearch/*` branches (ancient, from sessions 1-8)
   - All `pr/*` and `revert/*` branches (stale PRs)

7. **Replay observation**: Hub depletion causes 18% reward growth decline in last 400 steps. With 3A+5M at 8 agents, make_heart from 5 miners should partially offset this. The 4-agent replay (3A+1M) showed it more starkly.
