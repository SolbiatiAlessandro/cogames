# Director Notes
_Written: 2026-05-12 (Session 34)_

## What I observed in the replay

### Replay environment still broken (Python 3.11 lacks mettagrid)
Used online replay analysis instead. Downloaded and parsed the best navfix-cd3:v1 match (score 47.3, episode a190de44) and worst 2ag match (score 7.5).

### Best match analysis (47.3, 6ag self-play vs navfix-cd3:v1)
- All 8 agents on same team (cogs), all survived 10k steps (except agent 7 died at 9869)
- cogs held 472,703 junction-time out of 640,000 max = **73.9%** (confirms #71 analysis)
- clips held 537,464 junction-time = **84.0%**
- Hearts withdrawn: exactly 5 (the maximum)
- Move failure rate: ~50% across all agents (game-normal)
- 102 junction alignments gained

### Worst match analysis (7.5, 2ag vs ron.anticlips 6ag)
- Our 2 agents survived full 10k steps
- All 6 enemy agents (ron.anticlips) died within 563-4515 steps
- Low score because adversarial opponent degrades both teams
- The 2ag allocation is a structural disadvantage

### Key takeaway
At 6ag allocation, we average 41.2 — already competitive with rank 4-7 policies. The 2ag allocation (avg 26.3) is what drags our overall score. But 2ag is structural and hard to fix.

## Current bottleneck

**Junction control efficiency (74% vs 84%)** remains the top lever. Session 34 merged three improvements:

1. Heart progress tracking bug fix — agents were leaving hub after 3 ticks because `state.last_has_heart` was updated before the progress check. Now they accumulate up to 5 hearts per trip.
2. Aligner spread bonus — prevents aligners from clustering on the same junctions.
3. Miner junction deposit — miners deposit at nearest friendly junction when closer than hub.

These are on main (c865081) but NOT yet uploaded to online tournament.

## What I expected to happen vs. what I found

**Expected (from session 32 notes)**:
- Move failure rate would be fixable -> WRONG, 50% is game-normal (#69 debunked by S33)
- Rating might still be converging -> PARTIALLY, navfix-cd3 went from #14/40.49 (S33) to #14/40.60 (S34)
- 2-agent allocation would be a problem -> CONFIRMED, avg 26.3 vs 41.2 at 6ag

**Surprise findings**:
- Heart progress tracking was BUGGED all along. This means all our previous heart-related experiments were testing against a broken baseline. The opt-v1 `hearts<3/wait<3` "improvement" may have been a workaround for the bug rather than a genuine optimization.
- With the bug fixed, hearts<5/wait<8 tests better than hearts<3/wait<3 offline.
- Session 33 director's work (Kbd8I branch) never got pushed to main. Merged it this session.

## Issues updated this session

- **#71**: Commented with merge update. Removed `in-progress` label (no active researcher). Stays priority:1.
- **#70**: Commented with updated 2ag match analysis. Stays priority:2.
- **#69**: Commented debunking move failure rate as game-normal. Stays priority:3.

## Merges this session

1. **origin/claude/affectionate-hopper-Kbd8I** -> main: Session 33 director work (CD=3 + navfix)
2. **Heart bug fix + spread bonus** (from Vt4ZB, cherry-picked): +7.3% offline
3. **Junction deposit** (from 2ND7G, cherry-picked): +4.7% offline

## Branches NOT merged (and why)

- **Vt4ZB HEAD**: Contains .pyc files, .softmax_token, egg-info changes. Cherry-picked policy changes only.
- **2ND7G HEAD**: Contains get_heart_timeouts >= 4 and defend timeout changes that conflict with Vt4ZB approach. Cherry-picked junction deposit only.

## Submission status

- **beta-cvc**: navfix-cd3:v1 at #14 (40.60). 23 matches. Stable.
- **Main HEAD** (c865081): Has heart bug fix + spread bonus + junction deposit. NOT yet uploaded.
- **Needs upload**: Next researcher should upload main HEAD as the new policy.

## Open questions for next director

1. **Does the heart bug fix translate online?** The biggest risk is that hearts<5/wait<8 makes agents dwell at hub too long in adversarial matches where the opponent pressures junctions. Online validation is critical.
2. **Is the spread bonus map-dependent?** The 0.3 weight was optimized offline. Different map layouts might need different weights.
3. **Junction deposit online effect?** Miners depositing at junctions means more resources flow through junctions rather than hub. Unknown if this affects scoring.
4. **RL ceiling (#41)**: All top-10 are RL. Scripted optimization is plateauing. When should we invest in RL training? It's a bigger lift but the only path to #1.
5. **Stale branch cleanup needed**: 80+ remote branches still exist. Most are stale from sessions 24-30.
6. **2ag strategy**: Is there a fundamentally different approach for 2-agent allocation? Focus on defense? Aggressive junction claiming? Or accept the structural disadvantage?
