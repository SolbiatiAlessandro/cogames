# Director Notes
_Written: 2026-05-09 (Session 31, offline-to-online)_

## What I observed

### contamination-v64 CRASHED online (P0, #68)

The +15.2% offline improvement from the gear contamination fix (#64) is completely blocked from online deployment. All 8 qualifying matches across both seasons failed:

- **beta-cvc**: 4 matches, all `status=failed`, `error_type=crash`
- **beta-teams-tiny-fixed**: 4 matches, all `status=failed`, `error_type=crash`
- Error: `"received 1011 (internal error); then sent 1011 (internal error)"`
- All matches were solo qualifying (assignments=[0,0,0,0,0,0,0,0]), so the crash happens without any opponent interaction

This is a 100% crash rate, indicating a fundamental code error — likely an import, class definition, or early-initialization issue, not a runtime edge case.

### Root cause investigation (inconclusive)

I inspected all code changes between v52 (working) and contamination-v64 (crashing):

Files changed:
- `llm_skills.py` — `contamination_avoid_cells` field, `_safe_wander`, `_greedy_walk_toward_safe`, BFS avoidance
- `llm_miner_policy.py` — contamination detection, cell recording
- `aligner_agent.py` — `JUNCTION_ALIGN_DISTANCE=25`, 2 new dataclass fields
- `cross_role_policy.py` — `_expand_hazard_zone`, `_navigate_to_station_safe`

No obvious crash-causing bug found through code inspection:
- All imports are clean and available
- `from __future__ import annotations` is present where needed
- `dataclasses.replace` is properly imported
- All `getattr(state, 'contamination_avoid_cells', set())` calls are defensive

Possible causes I cannot rule out without server logs:
1. MettaGrid API mismatch between local and server versions
2. Bundle packaging error (stale or missing files)
3. A subtle runtime error in the new contamination code paths

### v52 online replay analysis (score 44.67, 10k steps)

Downloaded and analyzed replay `e566505e` (v52 + ron.anticlips.v5.baseline.b, cooperative):

| Metric | Value | Insight |
|--------|-------|---------|
| Hearts withdrawn | 5 | Extremely low — confirms aligner throughput bottleneck (#67) |
| Junction control | cogs 446,698 vs clips 214,190 (2:1) | Strong junction dominance |
| Resource deposits | 2969-3456 per element | Mining surplus, not a bottleneck |
| Agent survival (ours) | 4588-7499 steps | Die before 10k but far better than partner |
| Agent survival (partner) | 767-1767 steps | Partner agents die very early |
| Vibe transitions | 0 for all agents | Nobody uses change_vibe actions |
| All agents alive at end | Yes (8/8) | Agents survive in this match |

Key insight: Our agents outlive partner agents by 3-5x. The partner dying early means we need to be robust to carrying the team solo for most of the 10k steps.

### Leaderboard status

**beta-cvc (736 entries)**:
- v52: #39 (36.45), up from #40 (36.15) — score improved by 0.30 despite 24 new entries entering
- Gap to #1 (Softy:v96 at 41.86): 5.41 pts (12.9%), narrowed from 13.6%
- Top 5 unchanged: Softy:v96, slanky:v171, Paz-Bot-9000:v47, Gryffindor:v11, slanky:v165

**beta-teams-tiny-fixed (10 entries)**:
- No lessandro entries visible. Need to verify if v52 was submitted here.
- Top entries: Paz-Bot-9000:v76 (#1, 12.0), slinky:v6 (#2, 13.0)

### v52 match statistics (25 matches, beta-cvc)

- Average: 36.32 (up from 35.5 at session 30)
- Min: 6.32 (dedicated.ao:v1 — anomalously bad partner)
- Max: 54.46 (ron.anticlips)
- Variance still high: std deviation ~12 pts, driven by partner quality

## Offline observations

No new offline experiments since session 30. The latest TSV results are from EnIvJ:
- Baseline (v52): 2.849 avg reward (5-seed)
- Post-contamination-fix: 3.282 avg reward (+15.2%)
- 10-seed extended validation: avg 3.071, no regressions

The offline trajectory is stalled because the contamination fix can't be deployed online, and the next bottleneck (#67, aligner throughput) is logically blocked until deployment succeeds.

## Online observations

- v52 is slowly gaining ground: #39 (36.45) vs #40 (36.15) last session
- The cooperative scoring means partner quality dominates variance
- Our agent survival (4588-7499 steps) is a competitive advantage
- Zero vibe usage across the board — this might be a missed optimization or the game doesn't reward it

## Offline→Online gap

1. **Offline best**: 3.282/agent (commit d922520, contamination fix). **Online best**: #39, 36.45 (v52, pre-fix code).
2. **Gap is entirely caused by deployment failure**: The fix works offline (+15.2%) but crashes online (8/8 failed). This is not a strategic gap — it's a packaging/compatibility bug.
3. **If the crash were fixed**: Optimistic estimate is +3-5 rank positions (based on the 15.2% offline improvement), potentially reaching #35-37. This would narrow the gap to #1 from 12.9% to ~9%.
4. **Bottleneck**: 100% online (deployment crash), not offline (policy quality).

## Issues updated this session

- **#68**: CREATED (priority:0). contamination-v64 crashes online, 8/8 qualifying matches failed. P0 blocker.
- **#67**: DEMOTED to priority:2, commented with online replay data confirming aligner bottleneck (5 hearts in 10k steps). Blocked by #68.
- **#65**: Commented — cannot validate JUNCTION_ALIGN_DISTANCE=25 online until #68 resolved.
- **#62**: Commented with v52 junction control data (2:1 ratio). Blocked by #68.

## Branches NOT merged (and why)

No new branches with work since session 30. Branch status unchanged:
- **NNt07**: Superseded by EnIvJ
- **VZvye**: +0.7%, within noise
- **C4lUC, q8Otj**: hCVEi-contaminated
- **dCgfY**: No new work

Branch cleanup still needed (80+ remote branches).

## Submission status

- **beta-cvc**: v52:v1 live at #39 (36.45). contamination-v64:v2 CRASHED (8/8).
- **beta-teams-tiny-fixed**: contamination-v64:v1 CRASHED (4/4). v52 status unclear.
- **No new submission made this session** — cogames CLI installed but Python 3.11 environment can't build local package (requires 3.12). Need the local Mac environment (Python 3.12) for uploads.

## Open questions for next director

1. **Why does contamination-v64 crash online?** This is the #1 question. The next researcher on #68 should:
   - Run `cogames scrimmage` locally with current main code to see if it reproduces
   - Try a bisect submission: v52 + only JUNCTION_ALIGN_DISTANCE=25 (safe, no contamination logic)
   - If that works, add contamination changes incrementally to find the crashing change
   - Ask Softmax for server-side logs if possible

2. **Should we submit v52 to beta-teams-tiny-fixed?** We have no entries there. v52 is proven stable.

3. **Is the v52 score improving organically?** It went from 36.15 to 36.45 (+0.30) without any code change. This could be random variance or partner pool changes.

4. **Vibe transitions: missed optimization?** Zero agents use change_vibe. If vibes affect gameplay, this could be low-hanging fruit. If they don't, it's irrelevant.

5. **Branch cleanup**: Still 80+ remote branches. Consider deleting merged/superseded ones (NNt07, VZvye, etc.) next session.
