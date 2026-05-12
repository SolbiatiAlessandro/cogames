# Director Notes
_Written: 2026-05-11 (Session 33, offline-to-online)_

## Offline observations

### Branches merged this session
- **zwbgs** (CD=3 + cooldown clear): Fast-forward merge. `_MOVE_COOLDOWN` 6→3 gives +2.2% offline. `move_cooldowns.clear()` on skill switch gives +0.4%. 9 experiments total, only these 2 kept.
- **Qh03p navfix changes (cherry-picked)**: BFS-without-move-blocked fallback + FIFO eviction for move_blocked_cells (cap at 40). Applied manually to main. Did NOT merge wall-following, dodge, or directional-explore — these are in navfix-cd3-v2:v1 which regressed to #56.

### Branches NOT merged (and why)
- **Qh03p HEAD** (89ccb8a): Contains wall-following + dodge (discarded) + directional-explore + enemy recapture bonus. navfix-cd3-v2 (which includes later Qh03p changes) scored #56 vs navfix-cd3:v1 at #14. Something in the later additions regressed.
- **SamLl** (451be74): Junction dist split +2.5% offline but J=25 cascade is better online. Stale.
- **095mA** (09502f7): hub_weight=0.1 + map pollution. Regressed from opt-v1.
- **IgXg8**, **OPj3g**, **NNt07**, **VZvye**, **C4lUC**, **q8Otj**, **dCgfY**, **0S1xy**: All stale since S29-30.

### Offline TSV summary
- CD=3 baseline avg: 1097.2 (3-seed) vs CD=6 baseline: 1073.6 → +2.2%
- CD=3 + cooldown_clear: 1104.1 avg → +0.6% on top of CD=3
- All other CD=3 combinations (navshake, hub_rotation, bfs_agent_avoid, shared_cooldowns) regressed

## Online observations

### Leaderboard state (2026-05-11)
| Metric | Session 30 | Session 32 | Session 33 | Trend |
|--------|-----------|-----------|-----------|-------|
| Our best rank | #40 (v52) | #13 (opt-v1) | #14 (navfix-cd3) | Improving but plateauing |
| Our best score | 36.15 | 40.07 | 40.49 | +4.34 total |
| #1 score | 41.86 (Softy:v96) | 41.86 | 45.29 (Softy:v103) | Competitor accelerating |
| Gap to #1 | 5.71 (13.6%) | 1.79 (4.3%) | 4.80 (10.6%) | GAP WIDENED |
| Total entries | 712 | 712 | 782 | Growing |
| Our entries | ~10 | ~20 | 72 | Massive upload surge |

### Key policy performance
- **navfix-cd3:v1** (#14, 40.49, stddev 5.81, 21 matches): Very consistent, never drops below 27.6. But ceiling limited — max 48.4.
- **aligner-opt-v1:v1** (#18, 40.07, stddev 9.23, 23 matches): Previous best. Wider variance.
- **aligner-opt-v17:v1** (#21, 39.39): Close but not better.
- **navfix-cd3-v2:v1** (#56, 36.46): REGRESSED from v1 — later additions hurt.
- **v52:v1** (#54, 36.73, 65 matches): Long-term baseline, stable.

### Replay analysis — our high match (navfix-cd3, 48.39)
- 65 junctions, 10k steps, partner: dinky_bob:v12
- Cogs junction-time: 483,904/650,000 = **74.4%**
- Agent 0: 2147 steps active (died early), 48.1% move failure
- Agent 1: 7550 steps active, 50.0% move failure
- Zero vibe transitions (vibes set at init, not through in-game actions)

### Replay analysis — Softy:v103 (54.4)
- 8 agents, 10k steps, 6 Softy + 2 partner
- Cogs junction-time: 544,441 = **83.8%** of possible
- All Softy agents: 5200-6200 steps (CONSISTENT lifespans)
- 46-48% move failure rate (SAME as us)
- Zero vibe transitions (same behavior)

## Offline-to-Online gap

1. **Offline best**: 3.282 reward (8-agent, 3000 steps, contamination fix). **Online best**: #14, score 40.49.
2. **Gap widened**: Softy improved +3.43 pts (v96→v103) while we improved only +0.42 pts (opt-v1→navfix-cd3).
3. **50% move failure rate is NOT a differentiator** — both #1 Softy and us have the same rate. The offline researchers on #69 spent time on a red herring.
4. **Junction control efficiency is the real gap**: 74.4% vs 83.8% of junction-time. This maps to ~6 score points.
5. **Agent lifespan consistency**: Softy agents all run ~5500 steps; ours vary 2000-7500. Early deaths waste junction-holding capacity.
6. **Stddev gap**: Our 5.81 vs Softy's 16.53 means we're safe but never spectacular. We need ceiling-raising changes, not floor-raising.

## Current bottleneck

**Architectural ceiling of scripted policies.** All top-10 are RL. Our scripted policy has been optimized through 72 uploaded variants and is plateauing at #14. Two paths forward:

1. **Short-term**: Junction control efficiency (#71) — squeeze more from scripted approach
2. **Long-term**: RL training (#41) — the only path to top-10

## Issues updated this session

- **#71**: CREATED (priority:1). Junction control efficiency — the real gap to #1.
- **#41**: PROMOTED to priority:1. RL is the ceiling-breaker.
- **#69**: DEMOTED to priority:3. 50% failure rate is game-normal. Exhausted.

## Code merged this session

1. zwbgs branch (fast-forward): CD=3, cooldown clear
2. Manual cherry-pick from Qh03p: BFS-without-move-blocked, FIFO eviction
3. Main now has: contamination fix + hearts<3/wait<3 + CD=3 + cooldown clear + BFS relaxation + FIFO eviction

## Open questions for next director

1. **Why did navfix-cd3-v2 regress?** Need to isolate which Qh03p addition (wall-following? enemy recapture? directional-explore?) caused the #56 drop from #14. This determines whether further navfix experiments are worthwhile.
2. **Can junction targeting be improved without RL?** Analyzing which junctions are held longest in high-scoring matches could reveal a better targeting heuristic.
3. **Stale branch cleanup**: 80+ remote branches. NNt07, VZvye, C4lUC, q8Otj, IgXg8, dCgfY, 0S1xy, 095mA, SamLl, OPj3g, wf6SN all confirmed stale. Can be deleted.
4. **Should we submit from main?** Main now has all proven changes but hasn't been uploaded. navfix-cd3:v1 is the closest but was uploaded from a working copy. Submitting from main would confirm parity.
5. **Partner-quality sensitivity**: Our worst matches (27-29) are with weak partners. Is there a way to detect partner quality early and adapt strategy?
6. **Softy's improvement rate**: +3.4 pts in ~3 days. They're iterating fast with RL. We can't match this pace with scripted optimization.
