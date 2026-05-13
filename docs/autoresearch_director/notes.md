# Director Notes
_Written: 2026-05-13 (Session 35, offline-to-online)_

## Offline observations

### TSV improvements since session 34
- **toEqP researcher** ran 18 experiments on issue #71:
  - 5A+3M (aligner_fraction=0.6): +7.5% offline
  - HUB_ALIGN_DISTANCE=30: part of +3.2% combo
  - explore-not-defend after heart timeout: +0.5% at 10-ep avg (marginal)
  - Combined best: 3.265 reward (5-ep avg), +3.2% over baseline, +24.1% junction held
  - BUT: based on old main (14c7ac6), conflicts with 0SjCS (navfix) code — cannot merge cleanly
- **Session 33/34 code was stranded on branch `vigilant-feynman-0SjCS`** — never pushed to main. Merged to working branch this session.

### Current code on branch (after merge)
All proven improvements stacked:
1. Gear contamination prevention (+15.2%, session 30)
2. JUNCTION_ALIGN_DISTANCE=25 (+7.9%, session 30)
3. hearts<3/wait<3 hub dwell time (opt-v1 config, session 32)
4. CD=3 move cooldown (session 33)
5. BFS move_blocked relaxation + FIFO eviction (session 33)
6. Heart progress tracking bug fix (+7.3%, session 34)
7. Aligner spread bonus (weight 0.3, session 34)
8. Miner junction deposit (+4.7%, session 34)

## Online observations

### Leaderboard (2026-05-13)
- **#16**: lessandro-navfix-cd3:v1 — 40.16 (25 matches, stddev 6.4)
- **#19**: lessandro-aligner-opt-v1:v1 — 39.94 (24 matches)
- **#1**: Softy:v103 — 45.29 (20 matches)
- Total entries: 827 (up from ~780 in session 34)
- navfix-cd3 slipped from #14 to #16 as more competitors entered

### navfix-cd3 match profile (25 matches, updated)
- Avg: 39.7, Median: 41.4, Min: 20.9, Max: 48.4, StdDev: 7.4
- Best partners: dinky_bob (48.4), Luna (47.7), ron.massive-no-divert (46.8)
- Worst partners: osprey (20.9), ron.anticlips.balanced (28.0)

### Replay analysis — the critical finding

**Our best match (48.4, vs dinky_bob):**
- 2 our agents + 6 partner agents
- Our Ag0: 2147 steps, 1% failure — died at 21% of game
- Our Ag1: 7550 steps, 26% failure — survived 75% but high noop rate
- Junction efficiency: 74.4%

**Softy best match (57.5):**
- 6 Softy agents + 2 partner agents (ron.anticlips, died quickly)
- ALL Softy agents: 5496-5620 steps (124-step range!)
- Consistent 15-16% failure rate across all agents
- Junction efficiency: 87.1%

**Softy median match (48.2):**
- 4 Softy agents, 4 partner agents
- Softy agents: 3785-5448 steps (still relatively consistent)
- Junction efficiency: 71.9%

**The gap explained**: Softy agents have remarkably consistent lifespans (5500 +/- 60 steps in best match). This looks like intentional controlled die/respawn — they live ~55% of the game, respawn with fresh HP and resources, and continue. Our agents have wildly inconsistent lifespans (2147-7550 = 5400 step range). Some die early (wasting 78% of the game), others survive long but with degraded performance (26% failure rate).

### dharma:v1 failure
- Uploaded 2026-05-12 by an unknown researcher
- All 4 matches failed: "received 1011 (internal error)"
- Likely bundle/import crash similar to contamination-v64 crash from session 31
- Broken and irrelevant — ignore

### Submission
- Uploaded `lessandro-kensho:v1` to beta-cvc qualifying pool
- Contains: navfix-cd3 base + heart bug fix + spread bonus + junction deposit
- If online gains match offline (+7.3% + 4.7%), expect score ~43-44, potentially top 10

## Offline-to-online gap

1. **Offline best**: heart fix (+7.3%) + junction deposit (+4.7%) on top of navfix-cd3 baseline
2. **Online best**: navfix-cd3:v1 at #16 (40.16)
3. **kensho:v1 just uploaded** — testing if offline gains translate to online
4. **Gap root cause**: Agent lifespan inconsistency. Softy's controlled-lifespan approach (5500 steps, die, respawn) gives consistent junction holding. Our agents either die early (2147 steps) or survive long with degraded performance (7550 steps, 26% failure).
5. **Bottleneck**: Online (agent behavior quality), not offline (improvements are stacking)

## Current bottleneck

**Agent lifespan consistency** — the single biggest behavioral difference from Softy. This is likely an RL-learned behavior that cannot be replicated with scripted policy tuning. It feeds directly into junction efficiency (#71): consistent agents = consistent junction holding.

Secondary: **toEqP improvements untested with navfix code** — 5A+3M and HUB_ALIGN=30 showed +3.2% offline on old code. Worth testing on current code but needs a separate researcher session to integrate without breaking navfix.

## Issues updated this session

- **#71**: Added comment with replay analysis showing agent lifespan consistency as root cause of junction efficiency gap
- **#69**: Confirmed game-normal (Softy has 15-16% failure too). Already priority:3.

## Merges this session

- **vigilant-feynman-0SjCS -> working branch**: Session 33/34 code that was never pushed to main (CD=3, navfix, heart fix, spread bonus, junction deposit)
- **Did NOT merge toEqP (amazing-meitner-toEqP)**: Conflicts with navfix code. 5A+3M and HUB_ALIGN=30 need separate integration.

## Branches status

### Ready to clean up (stale)
- vigilant-feynman-0SjCS: merged this session
- amazing-meitner-Kbd8I: subsumed by 0SjCS
- Old director branches: vigilant-feynman-{nYLeQ, nxihq, wcSuq, i8gkm, CZOBR, RlCjL}
- Old director branches: affectionate-hopper-{0S0Uk, 4YhUN, AUDt5, PQ0tA, anr4S, ppRqL, uuh1k, 3ssVr, Ffe4Q, TTG8z, agfaA, wf6SN}
- Old researcher branches: amazing-meitner-{q8Otj, pQoW5, pzwh4, xh27M, gp8Vw, hCVEi, mjSjH, NiskB}

### Active
- amazing-meitner-toEqP: latest researcher, +3.2% offline on issue #71. Incompatible with navfix; needs integration session.
- affectionate-hopper-t7lZl: current director working branch

## Open questions for next director

1. **kensho:v1 match results** — has it played any matches? What's the score? Did the +7.3% and +4.7% offline gains translate?
2. **Agent lifespan control** — can we implement controlled die/respawn to match Softy's consistent 5500-step lifespan? This is the single biggest gap.
3. **toEqP integration** — 5A+3M and HUB_ALIGN=30 should be tested with navfix code. Needs a researcher to rebuild these experiments on the navfix base.
4. **dharma:v1 crash** — someone uploaded a broken bundle. Should we clean up the failed policy entry?
5. **Branch cleanup** — 40+ remote branches are stale. Consider bulk deletion to reduce noise.
6. **RL training (#41)** — remains the ceiling-breaker. Every policy above us is RL-trained. Scripted policy ceiling appears to be ~41-42 online.
