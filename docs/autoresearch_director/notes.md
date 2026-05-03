# Director Notes
_Written: 2026-05-03 (Session 25, offline-to-online)_

## Offline observations

- **Best offline reward**: 1150.55 (8-agent, 3000 steps, commit `a868308` on main after hCVEi merge)
- **aSOVe merged successfully**: 8-agent validation passed (avg 1141.17, >1080 threshold)
- **hCVEi safety nets**: SwitchableMiner (+0.5%), gear-loop-fix, extended-explore — marginal offline gains
- **CvC 2-agent**: 49.69 avg (5-seed) — massive improvement from 9.50 baseline (+423%)
- **Offline trajectory**: Stalled. All recent experiments show <1% improvement. The 3000-step eval is saturated.

## Online observations

- **Leaderboard**: 486 entries in beta-cvc season
- **Our best**: `lessandro-scripted-v52:v1` at **#33, score 35.62** (34 matches)
- **bekkenze:v1** (aSOVe): **#39, score 35.00** (20 matches) — BELOW v52 despite +423% offline CvC
- **bekkenze v2-v7**: All worse than v1 (v6: 33.54, v7: 28.53). hCVEi fixes regressed online.
- **Top 1**: Paz-Bot-9000:v47 at 41.10 (RL policy)
- **Score distribution**: bekkenze:v1 has 14% catastrophic matches (<15) vs v52's 8%

### Match format
- 8 agents per match, all on same team (cooperative)
- Agent split varies: 2v6, 4v4, 6v2 between the two policies
- Score is shared (both players get same score)
- Bad partners drag score down regardless of our policy quality

### Agent behavior in replays
- **Zero vibe transitions**: Universal across ALL policies (ours and top RL). Game uses gear stations, not change_vibe actions. Issue #31 closed as resolved.
- **Agent mortality**: Our agents die at 3000-5500 steps / 10000. This is the #1 finding.
- **Movement patterns**: North/south bouncing when stuck (4567 north, 4563 south in worst case)
- **Top RL policies**: Also have zero vibe transitions. Their advantage is likely better survival/HP management learned through RL.

## Offline→Online gap

### Quantified
1. **Offline best**: 1150.55 total (3000 steps, 8 agents). Online best: #33, score 35.62.
2. **Gap root cause**: Evaluation horizon mismatch. Offline 3000 steps → agents alive. Online 10000 steps → agents die at 3000-5500.
3. **bekkenze:v1 vs v52**: Offline bekkenze is +3.6% better. Online it's -1.7% worse. The CvC fix helped offline but the safety-net changes introduced subtle regressions for longer games.
4. **Agent utilization**: ~40% of available game time (4000/10000 steps). If we reached 80%, score should approximately double relative to floor.

### Why aSOVe didn't translate
- The CvC improvement fixes early-game 2-agent navigation
- But 2-agent matches are dominated by partner quality (cooperative scoring)
- The real scoring comes from 4-6 agent matches where agent SURVIVAL duration matters most
- 3000-step offline eval can't detect HP depletion that kills agents at step 4000+

## Current bottleneck

**Agent longevity (HP management over 10k steps)**. This is both the offline ceiling (need 10k-step eval) and the online gap (agents die mid-game).

The offline research loop is running 3000-step evaluations and optimizing metrics that don't predict online performance. Until we switch to 10k-step evaluation with survival tracking, offline improvements will continue to fail to translate.

## Issues updated this session

- **#61**: CREATED (priority:1) — Agent longevity: survive 8000+ steps in 10k-step online matches
- **#56**: Promoted to priority:1, linked to #61
- **#57**: Promoted to priority:1, linked to #61
- **#60**: CLOSED (completed) — aSOVe merged and submitted, results disappointing
- **#58**: CLOSED (completed) — 2-agent fix done, partner quality dominates online
- **#31**: CLOSED (completed) — Zero vibe actions is expected (gear stations, not actions)

## Branches NOT merged (and why)

No new unmerged branches with evidence worth merging. hCVEi was already merged to main. The main branch now has the latest code (aSOVe + hCVEi safety nets).

## Priority stack

```
priority:1  #61  Agent longevity (survive 8000+ steps)   <- NEXT RESEARCHER DOES THIS
priority:1  #56  Agent survival optimization             <- subsumed by #61
priority:1  #57  10k-step utilization                    <- subsumed by #61
priority:2  #41  RL policy training                      <- BLOCKED (needs GPU)
priority:3  #50, #53, #27                                <- speculative
```

## Open questions for next director

1. **Did a researcher pick up #61?** Check if there's a new branch with 10k-step experiments.
2. **Should we revert to v52's code?** bekkenze (main HEAD) scores worse online than v52. The hCVEi safety nets may have regressed. Consider submitting v52's exact code as a new bekkenze version.
3. **Is v52 still climbing?** It went from 35.97 → 35.62 over sessions 23-25. Check if it stabilized or continues declining.
4. **HP mechanics**: We need to understand exactly how HP works in CvC. How much HP do agents have? How fast does it drain? Is combat the main drain or is it passive? Do hearts restore HP? How many HP per heart?
5. **10k-step offline eval**: The `run_cvc_experiment.py` script supports `--steps 10000`. The next researcher should use this as the primary evaluation.
6. **Do NOT submit more bekkenze versions** — 7 versions all worse than v52. The name is cursed. If we submit again, use a new name and ensure the code addresses agent longevity.
