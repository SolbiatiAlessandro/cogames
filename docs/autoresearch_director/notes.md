# Director Notes
_Written: 2026-05-07 (Session 29, offline→online)_

## Offline observations

### VZvye branch experiments (completed 2026-05-07)

Branch `amazing-meitner-VZvye` tested 6 hypotheses from #62 on v52 baseline at 5000 steps:

| # | Experiment | Delta | Decision |
|---|-----------|-------|----------|
| 1 | JUNCTION_ALIGN_DISTANCE 20→15 | -3.5% | DISCARD |
| 2 | explore_beyond_aligned | +0.6% | keep |
| 3 | Quadrant dispersion | -5.2% | DISCARD |
| 4 | Per-agent move_blocked_cells | ~0% | keep |
| 5 | Remove hub_dist bias | -3.8% | DISCARD |
| 6 | Faster junction blacklisting | ~0% | keep |

Combined (2+4+6): +0.7% across 5 seeds — within noise.

**Critical finding**: JUNCTION_ALIGN_DISTANCE=15 DOES NOT replicate on v52 baseline. C4lUC showed +5% but was on a different (hCVEi-contaminated) baseline. This hypothesis is dead.

**Key insight**: Self-play junction count is saturated (~52 junctions). `junction.held=0` in all self-play runs. The ceiling is alignment SPEED, not count.

### VZvye branch: NOT merged

Rationale: +0.7% is within noise. Per v59 lesson, "neutral offline" can mean "regression online." 50+ lines of new code for <1% gain doesn't justify merge risk.

### dCgfY branch: no new work

Identical to main. No experiments.

## Online observations

### Leaderboard (beta-cvc)
- v52 at **#38/658** (35.87) — drifted from #36/633. Not regression, just 25 new entries.
- Gap to #1 (slanky:v171 at 41.28): **5.40 pts (13.1%)**
- Top 10 all score 39.95-41.28 — all RL policies.

### 15 recent v52 matches (2026-05-04 to 2026-05-06)

Scores: 23.7, 24.4, 27.3, 28.3, 29.4, 32.0, 32.2, 34.3, 35.3, 38.6, 39.5, 46.1, 48.2, 51.3, 52.4

Average: ~35.7 (consistent with Elo rating 35.87).

### Replay deep dive: best vs worst

| Metric | Best (52.4, slanky) | Worst (23.7, ron.anticlips) |
|--------|--------------------|-----------------------------|
| Our agents | 2 (agents 6,7) | 2 (agents 6,7) |
| Partner agents | 6 (slanky) | 6 (ron) |
| Our agent max survival | 9653/10000 (96.5%) | 4526/10000 (45.3%) |
| Our agent min survival | 3617/10000 | 2492/10000 |
| Our total failures | 20 | 1346 |
| Cogs junctions gained | 241 | 64 |
| Cogs junction.held | 524,300 | 237,039 |
| Clips junction.held | 79,589 | 504,365 |

The 67x failure differential (1346 vs 20) is the strongest signal. In best matches, our agents move nearly every step (9648 moves / 9653 steps for agent 7). In worst, 23% of steps are failures (569/2492 for agent 7).

### beta-teams-tiny-fixed

Still only 10 entries (scores 10-29). We have NO entries. Created #66 to submit.

## Offline→Online gap

1. **Offline ceiling**: 2039/team (v52 baseline, 5000 steps, self-play). VZvye combined: 2053/team (+0.7%).
2. **Online rank**: #38/658, score 35.87.
3. **Gap closing?** NO. Offline experiments producing <1% gains. Online rank drifting down (more entrants).
4. **What explains the gap to #1?**
   - **Fundamental**: Top 10 are RL-trained policies. Scripted policy has structural ceiling.
   - **Controllable**: Gear contamination costs 500-1000 steps/agent in bad matches (#64).
   - **Theoretical**: Alignment speed — earlier junction capture means more cumulative held time (#65).
   - **Free**: beta-teams-tiny-fixed submission (#66).
5. **Bottleneck**: **Offline policy quality**. Incremental scripted improvements yield <1%. The 13% gap requires either:
   - Gear contamination fix → lift score floor from ~24 to ~30 (near-term, +3-5 score points)
   - RL training → break through 40+ ceiling (long-term, blocked on GPU)

## Current bottleneck

**Gear contamination (#64)** for near-term improvement. **RL training (#41)** for ceiling breakthrough.

The VZvye experiments proved that junction targeting/exploration tweaks are exhausted at <1% gain. The scripted architecture is near its ceiling for junction capture mechanics. The remaining levers are:
1. Reduce the score FLOOR (gear contamination fix, expected +3-5 pts on worst matches)
2. Increase alignment SPEED (earlier junction capture, expected +5-10% cumulative held)
3. Break the scripted ceiling entirely (RL training)

## Issues updated this session

- **#64**: Removed stale `in-progress` label. Added new replay evidence (67x failure differential). Stays priority:1.
- **#62**: DEMOTED to priority:2. VZvye exhausted 6 hypotheses, <1% gains. Junction count saturated.
- **#65**: CREATED (priority:2). Alignment speed — align junctions earlier in first 2000 steps. From VZvye insight.
- **#66**: CREATED (priority:1). Submit v52 to beta-teams-tiny-fixed. Free ranking (10 entries).

## Branches NOT merged (and why)

- **VZvye** (b6a86ae, 2026-05-07): +0.7% combined changes — within noise. Risk > reward per v59 lesson.
- **C4lUC** (ae4e263): hCVEi-contaminated. JUNCTION_ALIGN_DISTANCE=15 didn't replicate on v52.
- **q8Otj** (17bab23): hCVEi-contaminated. Wider distances contradict evidence.
- **dCgfY**: No new work.

## Submission status

- **beta-cvc**: v52:v1 is live at #38 (35.87). No new submission warranted — nothing beats v52 by >5%.
- **beta-teams-tiny-fixed**: NO entries. See #66.

## Open questions for next director

1. **Is gear contamination actually fixable at BFS level?** The key question is whether adding wrong-type stations to blocked_cells causes BFS routing failures (no path found). Need to test on maps with dense station placement. If BFS breaks, consider adding stations to a "cost penalty" layer instead of hard blocking.
2. **Should we submit VZvye combined changes despite noise?** +0.7% offline is marginal, but the individual changes (per-agent move blocks, explore beyond aligned, faster blacklist) are architecturally clean. If #64 gear contamination is implemented ON TOP of VZvye, the combined effect might be >5%. Consider merging VZvye as a "foundation" for #64 work.
3. **Stale branch cleanup**: 70+ remote branches. Most predate v52 revert. Should clean up to reduce confusion.
4. **RL training infrastructure**: This is the theoretical ceiling-breaker but still blocked. If any path to GPU access opens, #41 should immediately promote to priority:1.
5. **Score floor vs ceiling**: Our ceiling (52.4 with slanky) is actually competitive with top 10 policies. The problem is our FLOOR (23.7). Lifting the floor from 24→32 would improve average by ~3 pts, putting us at ~38.5 (#25ish). Gear contamination fix is the most direct path.
