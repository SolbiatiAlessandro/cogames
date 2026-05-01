# Director Notes
_Written: 2026-05-01 (Session 23, offline-to-online)_

## What happened since Session 22

An autoresearcher (session 7T3EK) submitted the NiskB efficiency fixes as `lessandro-ohm-mani-padme-hum:v1` and iterated through v4. A second session (NWni3) continued experimentation and tried v5-v10. Key results:

### ohm-mani-padme-hum Online Results

| Version | Rank | Score | Matches | Key Change |
|---------|------|-------|---------|-----------|
| v1 | #58 | 33.32 | 20 | NiskB baseline |
| v2 | #49 | 33.66 | 8 | + aligner HP retreat 0.40/0.55 |
| v3 | #91 | 30.01 | 22 | + miner HP retreat 0.35 (REGRESSED) |
| v4 | #45 | 34.17 | 23 | Reverted miner HP, kept aligner retreat |
| v5-v10 | — | BROKEN | 0 | Server: `No module named 'cogames.games'` |

ALL ohm versions scored BELOW v52 (#29, 35.97) overall.

### The 2-Agent Problem (NEW — most important finding)

Autoresearcher 7T3EK discovered that NiskB beats v52 for 4+ agents (37.61 avg vs ~36) but catastrophically fails with 2 agents (9.16 avg). With `aligner_fraction=0.5`, 2 agents = 1 miner + 1 aligner. When paired with a weak partner controlling 6 agents, the team fails. ~35% of CvC matches assign only 2 agents — this drags the score from 37+ down to 33-34.

### Server-Side Breakage (NEW — BLOCKS everything)

ALL submissions after ~Apr 30 20:22 UTC fail with `No module named 'cogames.games'`. This is in the tournament server's Docker image, not our code. The autoresearcher tried setup_script shims, namespace packages, etc. — nothing works. We cannot submit ANY new policies until Softmax fixes this.

## Offline observations

- Best offline: 1118.60 (NiskB, commit 19d4b8b) — +3.6% vs v52's 1101.24
- NWni3 branch has additional experiments: hub-distance weight (+2.62%), aligner junction coordination. Not merged — can't validate online.
- Offline reward trajectory is flat. Multiple approaches tested (A*, NiskB, behavioral changes) — all produce 1-4% offline gains that don't translate online.

## Online observations

- Leaderboard: 463 entries (up from 453)
- #1: Paz-Bot-9000:v47 at 41.10 (unchanged)
- New entrant: slinky:v12 at #4 (40.67)
- v52: dropped #25 to #29 (35.97, was 36.18) — 29 matches, avg 34.42
- ohm v4 (our best new submission): #45 (34.17) — below v52

### Replay Analysis: ohm v4 Best Match (score 48.5, self-play with v57)

Agent survival is bimodal:
- Agents 0,3,4: survived 6115-7475 steps (good)
- Agents 1,2,5: survived 2322-2744 steps (died early)
- Pattern: half die early (2000-3000 steps), other half survive 6000-7500

This is different from session 22's analysis where most agents clustered around 5000-5500. The bimodal pattern suggests specific hazard encounters kill some agents early rather than gradual attrition.

### v52 Best Match (score 51.86 with dinky_fido)

- Agent 0: 3958 steps, 1.4% failure rate
- Agent 1: 8197 steps, 0.3% failure rate
- Both are v52 agents (2-agent match, partner=dinky_fido with 6 agents)
- When v52 gets 2 agents + a strong partner, it scores 51.86 — exceeding #1 average

## Offline-to-Online Gap Analysis

1. **Offline best**: 1118.60 (NiskB, commit 19d4b8b). Online best: #29, 35.97 (v52).
2. **Gap is NOT closing**: 4th consecutive offline improvement (NiskB) that fails to beat v52 online.
3. **Root cause identified**: The 2-agent match problem. NiskB is genuinely better for 4+ agents (37.61 vs ~36) but the 35% of 2-agent matches destroy the average.
4. **Server breakage blocks validation**: Can't even test fixes online.
5. **Bottleneck is now clearly online**, not offline. The online game has two factors we don't optimize for: (a) variable agent count (2 vs 4 vs 6), (b) partner quality.

## Current bottleneck

**Three stacked blockers:**
1. Server submission failure (#59) — EXTERNAL, blocks everything
2. 2-agent match handling (#58) — once server works, this is the biggest lever
3. Agent survival + 10k utilization (#56, #57) — secondary but significant

The scripted policy has hit its ceiling for "one-size-fits-all" approaches. The remaining gains require:
- Adaptive behavior based on agent count (2 vs 4 vs 6)
- Better late-game strategy (3k-10k steps)
- OR fundamentally: RL training (#41)

## Issues updated this session
- **#55**: Added director comment, downgraded to priority:2 + blocked (NiskB doesn't beat v52 overall, server broken)
- **#56**: Added replay analysis showing bimodal agent survival
- **#58**: CREATED (priority:1) — 2-agent match adaptive role assignment
- **#59**: CREATED (priority:1, blocked) — Server-side submission failure
- **#41**: Updated with current gap analysis

## Branches NOT merged (and why)
- **7T3EK**: Has aligner HP retreat, v4 revert. Results: ohm v4 at #45 — worse than v52 overall. Don't merge until 2-agent problem is solved.
- **NWni3**: Has online depletion reset, hub-distance weight, junction coordination. Can't validate online (server broken). Don't merge.

## Priority stack
```
priority:1  #59  Server submission failure (cogames.games)  <- BLOCKER
priority:1  #58  2-agent match handling                     <- BIGGEST ONLINE LEVER
priority:2  #55  NiskB online validation                    <- blocked by #59
priority:2  #56  Agent survival optimization
priority:2  #57  10k-step utilization
priority:2  #41  RL policy training                         <- blocked (GPU)
priority:3  #53, #50, #27-#31, #12-#23                     <- speculative/saturated
```

## Open questions for next director

1. **Server fix timeline**: Has the `cogames.games` module issue been reported to Softmax? Check Discord. If not fixed, we're stuck.

2. **2-agent adaptive strategy**: The autoresearcher tested all-miners (5.99), 1M+1A (162.04), all-aligners (47.27) for 2 agents. 1M+1A is optimal in self-play. But online the problem is partner quality, not our role split. Can we detect partner quality in-game and adapt?

3. **Should we merge HP retreat?**: ohm v2 (aligner HP retreat 0.40/0.55) improved 2-agent scores from 9.16 to 16.1 (+75%) with minimal 4/6-agent regression. This change might be worth merging to main as a defensive improvement.

4. **NWni3 experiments**: Hub-distance weight +2.62% and junction coordination are interesting but untested online. After server fix, consider cherry-picking these individually.

5. **Bimodal agent death**: Half of agents die at 2000-3000 steps, the other half survive 6000+. What specific event kills them? Combat damage from clips ships? Walking into a hazardous area?

6. **Leaderboard score decay**: v52 dropped from 36.18 to 35.97 (29 matches). Is this noise from new partner matchups, or is competition getting stronger?
