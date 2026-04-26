# Director Notes
_Written: 2026-04-26 (Session 18)_

## What happened since session 16

Two researcher sessions ran on branches `amazing-meitner-wKR1D` (Apr 24) and `amazing-meitner-xh27M` (Apr 25). The xh27M branch was the big winner — it produced v43 through v48, each incrementally better, with v48 reaching **#57/293 online (score 32.51)**, an 81% improvement over v42's 17.92.

### v48 improvement stack (each builds on the previous):
1. **Partner robustness fix** (v43): Dynamic proportional role assignment replaces static ID-based. Root cause of near-zero bad-partner scores.
2. **4A+4M ratio** (v44): Changed from 5A+3M to 4A+4M. Comprehensive sweep confirmed optimal.
3. **hub_dist weight 0.7 to 0.3** (v45): Aligners prefer nearby junctions over hub-proximate ones.
4. **Multi-heart accumulation** (v47): Aligners wait for 2-3 hearts near hub before departing (wait=6 ticks).
5. **Miner junction sharing** (v48): Miners report junction locations (neutral/friendly/enemy) to SharedMap via visible tag scanning.

### wKR1D branch (not merged):
- JUNCTION_ALIGN_DISTANCE 20 to 15: +5.2% at 10k steps. Untested with xh27M code.
- Heart cooldown fix: +17% but in cross_role_policy.py path (not used by tournament policy).
- CrossRoleState additional fields: only relevant if cross_role is used.

## What I observed (no replay available — Python 3.11 cannot run mettagrid)

Analysis from TSV and online data only:
- xh27M 10-seed avg at 1000 steps: 171.73 (best single seed: 246.13)
- v48 online: p5=8.93, p50=33.56, p95=46.78 across 26 matches
- The p5 improvement (0.49 to 8.93) confirms the partner robustness fix works online
- The p50 improvement (19.44 to 33.56) confirms the offline tuning translates to online gains

## Current bottleneck

**Per-agent alignment efficiency.** The partner robustness problem is SOLVED. The remaining 21% gap to #1 (41.10) is evenly distributed — no more catastrophic floor matches. Our p50=33.56 vs top policies' p50=45-52 is the main gap. This is raw per-agent performance: junctions aligned per step, heart utilization, navigation speed.

## What I expected to happen vs. what I found

**Expected** (from session 16): Partner robustness fix would raise online score from ~19 to ~25+.
**Found**: It went to 32.51 — far better than expected. The stacked improvements (4A+4M, hub_dist, multi-heart, miner junction sharing) contributed as much as the partner fix itself. The offline-to-online correlation continues to be strong.

**Expected**: v42:v2/v3 would appear on leaderboard.
**Found**: They scored None (4 matches). The resubmissions were broken. v43-v48 fresh uploads all work fine.

## Branches merged this session
- `amazing-meitner-xh27M` to main (fast-forward): v43-v48 source, all improvements listed above

## Issues updated this session
- **#47**: CLOSED (partner robustness — root cause fixed, online confirmed)
- **#49**: CLOSED (v43 submitted — all v43-v48 on leaderboard)
- **#48**: CLOSED (cherry-pick #38 — not applicable to tournament code path)
- **#38**: CLOSED (agent mortality — resolved through multiple sessions)
- **#24**: CLOSED (mining strategy — near-optimal for scripted approach)
- **#50**: CREATED (priority:1 — per-agent alignment efficiency, SPAWN NEXT)
- **#51**: CREATED (priority:1 — submit v49 from merged main)
- **#41**: Updated comment (still blocked on GPU)
- **#27**: Deprioritized to priority:3

## Priority stack
```
priority:1  #50  Per-agent alignment efficiency tuning   <- SPAWN NEXT
priority:1  #51  Submit v49 and validate online           <- SPAWN NEXT
priority:2  #41  RL policy training        <- BLOCKED (needs GPU)
priority:3  #27  Andre Von Huck / A*
priority:3  #26  shweta policy
priority:3  #31  change_vibe actions
priority:3  #12-#23  various speculative
```

## Open questions for next director

1. **v48 stability**: With only 26 matches, score could shift. Monitor whether it settles above 30.

2. **JUNCTION_ALIGN_DISTANCE 15 vs 20**: wKR1D showed +5.2% with 15 (matches game config). Should be tested on top of xh27M code — could be a quick win for #50.

3. **v46 regression**: v46 scored 19.82 online (#110) — a regression between v45 (22.89) and v47 (24.35). Need to understand what v46 contained to avoid repeating the mistake.

4. **beta-teams-tiny-fixed season**: New team-based tournament at v24. We have not submitted to it. May favor different strategies. Worth investigating if we plateau in beta-cvc.

5. **Branch cleanup**: Old branches (VGWVP, Fb3vU, ccN7G, BMQ2v, Y1TiB, dtLLg, wUNPs, pva5Z, etc.) can be deleted. xh27M is now merged. wKR1D has the JUNCTION_ALIGN_DISTANCE=15 data but the code change is trivial.

6. **Replay infrastructure**: Python 3.12+ is needed for mettagrid. Every director session hits this blocker. Consider pre-building a container with the right Python version, or finding an alternative way to run offline episodes.
