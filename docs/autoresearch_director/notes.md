# Director Notes
_Written: 2026-05-15 (Session 34, offline-to-online)_

## Offline observations

### Merge: evyIm branch into main
- Merged `claude/amazing-meitner-evyIm` (8 commits ahead)
- Single code change: `stuck_threshold` 20 → 15 in `machina_llm_roles_policy.py`
- Online evidence: #5 on leaderboard (41.85), best non-Softy policy

### Offline best unchanged
- Still 3.282 total reward (5-seed avg, d922520, v52 + contamination fix)
- toEqP achieved 4.751 offline (+76.6%) but is #275 online (27.18) — confirms offline-online gap

### No new offline experiments worth merging
- AX5WP branch: L2 distance fix + explore consecutive fails tracking. #11 online but combined with stuck15 regresses
- U0G66 branch: L2 fix + patrol mode removal. #29-132 online. Not competitive
- toEqP branch: 165 commits ahead. #261/#275 online. Catastrophic offline-online gap
- issue-71 branch: 2 commits, just starting. No results yet

## Online observations

### Leaderboard (beta-cvc, 928 entries)
| Rank | Score | Policy | Matches |
|------|-------|--------|---------|
| #1 | 45.29 | Softy:v103 | 20 |
| #2 | 43.58 | Softy:v111 | 22 |
| #5 | **41.85** | **evyIm-73a-stuck15:v1** | 8 |
| #11 | 40.85 | ax5wp-74a-hubl2-def-enemy:v1 | ~15 |
| #18 | 40.49 | lessandro-navfix-cd3:v1 | ~30 |

5 of our policies are in the top 20. 160 total policies submitted by us.

### evyIm-73a-stuck15 match analysis (8 matches)
- Avg: 41.85, Stddev: 7.1, p5: 21.4, p95: 46.6
- Very consistent: no matches below 21 (vs Softy's floor of 5.3)
- Ceiling capped at ~46 (vs Softy reaching 57+)
- High-score match (45.09): 66 junctions, cogs held 450,858 (69%), 5 hearts withdrawn
- Only 8 matches — rating may shift with more data

### Replay analysis (score 45.09 match)
- 8 agents total: 2 ours (evyIm), 6 partner (ax5wp-73k)
- Agent lifespans: 1877-7269 steps (significant variance, some die early)
- Cogs held 450,858 vs Clips held 551,066 junction-steps
- Only 5 hearts withdrawn — standard hub depletion pattern
- 100 junctions gained, 1384-1461 resources deposited per type

## Offline-to-online gap

### Current state
1. **Offline best**: 3.282 (5-seed avg, contamination fix). Not changed since session 30.
2. **Online best**: #5, score 41.85 (evyIm-73a-stuck15:v1, 8 matches)
3. **Gap to #1**: 3.44 pts (7.6%) — Softy pushed from 41.86 to 45.29

### Gap diagnosis
1. The gap is **architectural**: scripted ceiling at ~42, RL ceiling at ~57 (p95)
2. **Parameter stacking regresses**: U0G66 combo (#29) < either component (#5, #11). Same as kensho (#55 < navfix #18). See #74.
3. **Offline-online correlation**: Weak. toEqP is +76.6% offline, -35% online (#275). stuck_threshold=15 has no special offline advantage but is #5 online.
4. **Online-first methodology confirmed**: A/B testing 60+ variants online found the winner that offline testing missed.

### Is the gap closing?
- Session 30 to 34: We went from #40 (36.15) to #5 (41.85) = +15.8% absolute improvement
- But #1 also improved: 41.86 to 45.29 = +8.2%
- Our rank improved dramatically (#40 to #5) but the gap to #1 widened (1.79 to 3.44 pts)
- Within scripted framework: GAP IS NOT CLOSING. Need architectural change (RL).

## Current bottleneck

**Architectural ceiling.** The scripted policy with BFS navigation and LLM planning has hit its performance ceiling at ~42 average. Evidence:
- 60+ online variants tested; best is a single-parameter change
- Combining improvements always regresses
- p95 capped at 46.6 vs RL policies reaching 57+
- The gap is in late-game sustained efficiency over 10k steps

**Path forward**: RL training (#41) or accept #5 position.

## Issues updated this session

- **#74**: CREATED (priority:1). Scripted ceiling documentation + combination regression pattern
- **#73**: DEMOTED to priority:2. toEqP online results are catastrophic (#261/#275)
- **#71**: DEMOTED to priority:2. Junction control marginal gains
- **#41**: KEPT at priority:1. RL training is the only ceiling-breaker
- **#70**: DEMOTED to priority:3. Even top policies struggle at 2-agent

## Merges this session

- **evyIm branch into main**: stuck_threshold 20 to 15. Reached #5 on leaderboard.

## Branches NOT merged (and why)

- **AX5WP** (14 ahead): L2 fix + explore fail tracking. #11 online but regresses when combined with stuck15.
- **U0G66** (4 ahead): L2 fix + patrol removal. #29-132 online. Not competitive with evyIm.
- **toEqP** (165 ahead): 6 cumulative changes, +76.6% offline, #275 online. DO NOT MERGE.
- **issue-71** (2 ahead): Just started, no results.

## Submission status

- **beta-cvc**: evyIm-73a-stuck15:v1 at #5 (41.85). 8 matches. Best ever.
- No new submission needed — evyIm-73a is already uploaded and performing.

## Open questions for next director

1. **Has evyIm-73a stabilized?** With only 8 matches, the rating could shift. Check if score is still ~42 after 20+ matches.
2. **Can we get RL training started?** #41 is the only path to top-3. GPU is the blocker. Any available compute?
3. **Should we clean up branches?** 100+ remote branches. Many confirmed stale.
4. **What's happening in the wider tournament?** Softy pushed 4+ new versions since session 30. They're iterating on RL training.
5. **Is the combination regression pattern breakable?** 60+ variants suggest unlikely, but untested 2-change combos remain.
