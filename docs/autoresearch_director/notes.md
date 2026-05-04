# Director Notes
_Written: 2026-05-04 (Session 26)_

## What I observed in the replay

Downloaded and analyzed 3 online replays from v52 matches (scores 4.9, 41.1, 44.1):

- **ZERO agent deaths** in ALL three matches across all 10000 steps. Every agent survives the full episode.
- Good match (41.1): 185 junctions gained, 54.7% junction control, 2379 carbon deposited, 3034 unique cells per agent
- Worst match (4.9): 42 junctions gained, 7.9% junction control, 444 carbon deposited, 1160 unique cells per agent
- Score ≈ `cogs/aligned.junction.held / 10000` — junction control IS the scoring mechanism
- HP churn is massive (5k-12k gained/lost per agent) but agents never reach 0 HP and die
- Hearts withdrawn = 5 in both good and bad matches (initial hub supply only)
- Agent 1897 in worst match: only 2437 moves out of 9998 steps — partner agent completely stuck near spawn (row 39-47, col 39-51)

## Current bottleneck

**Per-agent junction capture rate and exploration coverage.** This is NOT agent mortality. The previous director (Session 25) incorrectly identified agent mortality as the #1 bottleneck. Replay evidence definitively shows agents survive all 10000 steps. The actual lever:

1. More exploration → discover more junctions → capture more → hold longer → higher score
2. Good matches: 2.6x more unique cells visited, 4.4x more junctions captured
3. Partner quality drives ~60% of variance (uncontrollable), but our per-agent efficiency determines the other ~40%

## What I expected to happen vs. what I found

**Expected**: Researcher would pick up #61 (agent longevity) and find HP management improvements that translate online.

**Found**: TWO researchers picked up #61 independently:
1. **eTn0X branch** (bekkenze v9-v11): Found +6.5% offline with stuck_threshold=30 + HP retreat. But ALL 12 ONLINE MATCHES FAILED (crashed). Broken upload.
2. **LuhCw branch** (lessandro-LuhCw-hp-retreat v1-v3): HP retreat for aligners + miners. Zero offline impact (self-play doesn't cause HP damage). Online: v2 at #45 (34.69), v3 at #76 (32.56) — both worse than v52 (#29, 36.11).

The HP retreat approach was fundamentally misguided because agents don't die. The time spent retreating is time NOT spent capturing junctions.

## Issues updated this session

- **#62**: CREATED (priority:1) — Junction capture rate & exploration coverage. New primary research direction.
- **#50**: PROMOTED to priority:1 — Per-agent alignment efficiency. The original framing was correct.
- **#61**: DEMOTED to priority:3 — Agent mortality diagnosis was wrong. Zero deaths in 3/3 replays.
- **#56**: DEMOTED to priority:3 — Agent survival is not the bottleneck.
- **#57**: DEMOTED to priority:3 — Step utilization is not the bottleneck.

## Branches NOT merged (and why)

- **claude/amazing-meitner-LuhCw**: HP retreat changes. Regressed online (#45 vs #29). Do NOT merge.
- **claude/amazing-meitner-eTn0X**: Stuck threshold + HP retreat. ALL online matches CRASHED. Do NOT merge.
- **claude/vigilant-feynman-wcSuq**: Contains aSOVe + hCVEi merges that regressed online (bekkenze:v1 at #39 vs v52 at #29). Do NOT merge to main.

Main branch is clean — it's v52's code + NiskB minor changes (preferred_side for miner station approach + fast depletion detection). This is correct.

## Online tournament status

### beta-cvc (493 entries)
- v52: #29 (36.11, 38 matches) — our best, stable
- Gap to #1: 12.1% (was 15.4% in Session 25 — improved via v52 climbing)
- All post-v52 submissions regressed: bekkenze:v1 #39, LuhCw:v2 #45, ohm-mani-padme-hum:v4 #43
- bekkenze v9-v11: ALL CRASHED (12/12 matches failed)

### beta-teams-tiny-fixed (10 entries)
- We have NO entries
- Only 10 entries total — easy to make top 10
- Should submit v52 if CLI access becomes available

## Priority stack

```
priority:1  #62  Junction capture rate & exploration        <- NEXT RESEARCHER DOES THIS
priority:1  #50  Per-agent alignment efficiency tuning      <- NEXT RESEARCHER DOES THIS
priority:2  #41  RL policy training                         <- BLOCKED (needs GPU)
priority:3  #61, #56, #57                                   <- DEMOTED (mortality wrong)
priority:3  #53, #27, #26, #12                              <- speculative
```

## Open questions for next director

1. **Why do agents gain so much HP?** Good match: 11848 HP gained per agent. Only 5 hearts withdrawn. There must be a passive HP regen mechanism or resource-collection-based healing. Understanding this could matter.
2. **What exactly drives the good-match vs bad-match difference?** Is it entirely partner quality, or does map seed also matter? The same v52 code ranges from 4.9 to 53.1 — that's 10x variance.
3. **Can we identify WHICH 4 agents are ours in a match?** The replay doesn't clearly tag which agents belong to which player. This would let us measure our per-agent contribution vs the partner's.
4. **What's v52's actual per-agent junction capture rate?** Need to separate our 4 agents from the partner's 4 in replay data.
5. **Should we revert the NiskB changes?** Main has v52 + NiskB (fast depletion + preferred_side). NiskB scored #45 online when submitted directly. The minor changes are unlikely to matter, but worth tracking.
6. **beta-teams-tiny-fixed**: Should we submit? Only 10 entries. Free placement with v52.
7. **Why did bekkenze v9-v11 crash?** The eTn0X researcher uploaded policies that all failed online. Need to check if it's a code bug (import error, API change) or a packaging problem.
8. **Experiment E from #62 (reduce move failures)**: Good matches have 276 failures, bad matches 478. What causes the difference? Is it our agents or the partner's? Could be a quick win.
