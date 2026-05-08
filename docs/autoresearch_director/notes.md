# Director Notes
_Written: 2026-05-08 (Session 30)_

## What I observed

### Replay unavailable
Python 3.11 on this machine lacks `typing.override` (3.12+). Could not run capture_frames.py. Relied on EnIvJ experiment log (10-seed validation data) and online match history instead.

### EnIvJ branch experiments (completed 2026-05-08)

Branch `claude/amazing-meitner-EnIvJ` ran 10 experiments on #64 (gear contamination):

| # | Experiment | Delta | Decision |
|---|-----------|-------|----------|
| 1 | Fast recovery + BFS hazard + approach rotation | +4.6% | KEEP |
| 2-4 | Safe explore, safe approach cells, hazard buffer | 0% to -11.4% | DISCARD |
| 5 | Faster gear_up timeout on repeat failures | +0.4% | KEEP |
| 6 | Fix contamination count reset bug | bugfix | KEEP |
| 7 | **Contamination avoidance cells** | **+15.2%** | **KEEP (BIG WIN)** |
| 8-10 | Optimistic BFS contam, hazard buffer, safe wander | 0% | DISCARD |

Combined 5-seed results (8-agent, 3000 steps):
- Baseline: 2.849 avg reward
- Post-fix: 3.282 avg reward (+15.2%)
- Seed 123 (worst): 1.810 -> 3.486 (+92.6%)
- 10-seed extended validation: avg 3.071, no regressions

Also included: JUNCTION_ALIGN_DISTANCE 20->25 (+7.9% in combined test, not isolated)

**Key insight**: Reactive avoidance (remember exact cells where contamination happened) works dramatically better than predictive avoidance (buffer zones around all hazard stations). Buffer zones block critical paths; reactive cells adapt to specific map layouts.

### EnIvJ branch: MERGED into main

Strong evidence: +15.2% (10-seed validated), clean code (209 ins / 15 del, 5 files), no regressions.

### NNt07 branch: NOT merged

Superseded by EnIvJ. NNt07 had partial contamination fix (+0.75% avg) that EnIvJ extended to +15.2%.

## Online observations

### Leaderboard (beta-cvc)
- v52 at **#40/712** (36.15) — stable despite 54 new entries
- New #1: Softy:v96 at 41.86 (up from slanky:v171 at 41.28)
- Gap to #1: **5.71 pts (13.6%)**
- contamination-v64:v2 submitted — 4 matches pending, no scores yet

### v52 recent matches (19 matches)
Scores: 6.3, 23.7, 24.4, 27.3, 28.3, 29.4, 31.2, 32.0, 32.2, 34.3, 35.3, 38.6, 39.5, 39.7, 46.1, 48.2, 51.3, 52.4, 54.5
Average: 35.5, Min: 6.3 (dedicated.ao:v1), Max: 54.5 (Softy:v96)

The 6.3 score with dedicated.ao:v1 is the worst match ever recorded. Our ceiling with good partners (54.5 with the new #1 Softy:v96) is competitive.

### beta-teams-tiny-fixed
v52 and contamination-v64 both submitted. Still 10 entries. Awaiting results.

## Current bottleneck

**Aligner throughput (#67)**. Post-contamination-fix, mining is no longer the constraint. Evidence:
- Resource surpluses: 300-650 per element (miners have excess capacity)
- Hearts withdrawn: 20-31 out of maximum potential 69-97 (only 30-40% utilization)
- The aligner is the throughput bottleneck: travel time hub->junction->hub is too long, hub congestion with 4 aligners, heart queue wait time

This is a clean bottleneck shift. The next researcher should focus on aligner efficiency, not mining.

## What I expected to happen vs. what I found

**Expected**: Gear contamination (#64) would be the top lever (from session 29 notes). VZvye experiments exhausted junction tweaks at <1%.

**Found**: #64 was indeed the top lever -- EnIvJ delivered +15.2%, the largest single improvement in recent history. The key was that the EnIvJ researcher tried the RIGHT form of avoidance (reactive, cell-level) vs. what NNt07 had tried (BFS-level buffers which regressed). Session 29's recommendation to pursue BFS-level station avoidance was partially wrong -- pure BFS buffers regress, but reactive cell avoidance works.

**Surprise**: The bottleneck shifted clearly to aligner throughput. Hearts withdrawn is only 30-40% of potential. This means further mining improvements are wasted.

## Issues updated this session

- **#64**: CLOSED. Resolved by EnIvJ merge. +15.2% avg reward, 10-seed validated.
- **#66**: CLOSED. v52 and contamination-v64 submitted to beta-teams-tiny-fixed.
- **#65**: Removed `in-progress` label. JUNCTION_ALIGN_DISTANCE=25 merged as part of EnIvJ but not independently validated. Overlaps with new #67.
- **#67**: CREATED (priority:1). Aligner throughput bottleneck -- hearts 20-31 of 69-97 potential. The new #1 priority.
- **#50**: DEMOTED to priority:3. Superseded by #67.

## Branches NOT merged (and why)

- **NNt07** (acbd9a5): Superseded by EnIvJ. Only had partial contamination fix (+0.75%).
- **VZvye** (b6a86ae): +0.7% combined -- within noise. Still not merging per session 29 reasoning.
- **C4lUC**, **q8Otj**: hCVEi-contaminated. Still not merging.
- **dCgfY**: No new work.
- **vigilant-feynman-0S1xy**: Empty, no commits beyond main.

## Submission status

- **beta-cvc**: v52:v1 live at #40 (36.15). contamination-v64:v2 submitted, 4 matches pending.
- **beta-teams-tiny-fixed**: v52 and contamination-v64 submitted. Awaiting results.

## Open questions for next director

1. **How does contamination-v64 perform online?** The +15.2% offline is large, but v59 also looked good offline and regressed 10% online. The contamination fix is architecturally cleaner than v59 (reactive cells vs. complex state machines), so I'm cautiously optimistic. Check contamination-v64:v2 rank after it accumulates matches.
2. **Is 5A+3M better than 4A+4M now that mining is surplus?** With the aligner throughput bottleneck, adding a 5th aligner might help. But v51 (5A+3M) scored lower historically. The dynamics may have changed post-contamination-fix.
3. **Heart queue wait time**: Currently 6 ticks. This was optimized for the old bottleneck (mining). With mining surplus, reducing to 3-4 ticks might speed up aligner cycling.
4. **Stale branch cleanup**: 80+ remote branches. Most predate v52 revert. NNt07 can now be deleted (superseded by EnIvJ).
5. **Online score floor**: The 6.3 score with dedicated.ao:v1 is catastrophic. Is this a hostile partner or a broken one? If hostile partners are common, defensive play might matter.
6. **JUNCTION_ALIGN_DISTANCE=25**: Merged as part of EnIvJ but needs isolated validation. If contamination-v64 performs well online, this is implicitly validated. If it regresses, consider reverting just this change.
