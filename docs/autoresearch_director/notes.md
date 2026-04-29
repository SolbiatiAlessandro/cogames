# Director Notes
_Written: 2026-04-29 (Session 21 — offline-to-online)_

## Offline observations

### gp8Vw researcher (v51-v58 sweep)
Systematic online validation sweep after v49's regression:
- v51 (5A+3M + phantom fixes): 3-seed avg 1060.91 at 3000 steps → online #94, 28.12
- **v52 (4A+4M + phantom fixes): 3-seed avg 1101.24 → online #23, 36.35 (NEW BEST)**
- v53 (exact v48 params): 1105.99 → online #73, 31.48 (worse!)
- v54 (max_hearts<3): 1049.57 → online #53, 33.26
- v55 (defend queue): 1101.43 → online #41, 34.31
- v56 (transit stuck fix): 1083.15 → online #67, 32.12
- v57 (HP retreat): 1083.15 → online #79, 30.98
- v58 (enemy priority): 1083.15 → online #72, 31.67

Key: v52 wins online despite v53 having marginally better offline reward (1105.99 vs 1101.24). Offline reward is a weak predictor of online rank.

### b3onP researcher
Investigated v49 regression. Found v50 (submitted from old main) was catastrophic (#123, 19.03). Good diagnostic work.

## Online observations

### Leaderboard (2026-04-29)
- 436 entries (up from 371 in session 20)
- #1: Paz-Bot-9000:v47 at 41.10 (unchanged)
- **#23: lessandro-scripted-v52:v1 at 36.35** (NEW — up from #56)
- #41: lessandro-scripted-v55:v1 at 34.31
- #48: lessandro-scripted-v48:v1 at 33.61 (was #56)
- Top 22 are all RL-based policies

### v52 match analysis (23 matches)
- p5=16.7, p50=37.6, p95=51.9
- Best: 53.1 with dinky_chad (cooperative RL policy)
- Worst: 4.9 with ron.whoops
- Floor improved significantly: p5 went from 7.2 (v48) to 16.7 (v52)
- With good partners (mammet, dinky, id_assigned), consistently scores 37-53

### Online replay analysis (v52 + mammet:v244, score 43.0 each)
- 8 agents, 10,000 steps, all survived (0 deaths)
- cogs junction held: 430,419 vs clips: 436,367 (nearly even!)
- 98 junctions gained total
- Our agents (4-7): ~97% move efficiency, very few noops (78-131 out of 5000+ steps)
- mammet agents (0-3): ~78% move efficiency, many noops (1064-1972)
- Both policies: zero change_vibe actions (roles assigned via gear stations, confirmed)
- Average 1019 unique cells visited per agent — good exploration

## Offline→Online gap

### The allocation insight (CRITICAL)
This is the most important finding of session 21:

| Allocation | Offline 1k-step 10-seed | Offline 3k-step 3-seed | Online rank | Online score |
|------------|------------------------|----------------------|-------------|-------------|
| 3A+5M (v49) | 251.36 (**best**) | 1061.50 | #66 | 32.16 |
| 5A+3M (v51) | — | 1060.91 | #94 | 28.12 |
| 4A+4M (v52) | — | 1101.24 | **#23** | **36.35** |

**4A+4M is 13% better online than 3A+5M despite being offline-equivalent or slightly worse at 1k steps.** The cooperative CvC format rewards balanced teams because:
1. Partners provide the other half of agents — if we're miner-heavy and partner is also miner-heavy, nobody aligns
2. 4 aligners cover more junction area than 3, reducing junction downtime
3. 4 miners are sufficient when max_hearts=4 allows efficient heart collection

### Why v53 (exact v48 params) was WORSE than v52
v52 uses hub_dist=0.2 (current code) and max_hearts=4. v53 restored v48's hub_dist=0.3 and max_hearts=max(2). Online showed v52 > v53 (36.35 vs 31.48), meaning the newer param values are genuinely better — it was only the ALLOCATION that v48 got right.

### Gap quantification
- v48 → v52: +8.2% (phantom fixes + correct params with same 4A+4M allocation)
- v52 → #1: 11.6% gap remaining
- v52's p95 (51.9) exceeds #1's average (41.1) — with the right partner we're already competitive

## Current bottleneck

**Scripted policy ceiling reached.** The gp8Vw researcher tested 8 variants and found no improvement beyond v52. All behavioral additions (defend queue, transit stuck, HP retreat, enemy priority) regressed online. The remaining options are:

1. **A* pathfinding** (#54, priority:1): Replace BFS with A* using Manhattan heuristic and wall memory. Should reduce the 1255-step average stuck time. Accessible without GPU.
2. **RL training** (#41, priority:2): Still blocked on GPU. Top 22 policies are all RL.
3. **Navigation efficiency tuning** within current BFS: diminishing returns after cooldown bypass fix.

## Issues updated this session
- **#52**: CLOSED — v49 validated (regressed), v52 new best via gp8Vw sweep
- **#50**: Downgraded to priority:3 — primary metric achieved (36.35 > 36.0)
- **#41**: Updated with online context — RL is the clear path past #23
- **#53**: Commented — requires RL infrastructure, priority:3
- **#54**: CREATED (priority:1) — A* pathfinding to close remaining gap

## Branches merged this session
- `amazing-meitner-gp8Vw` to main (up to commit 0c947d7): v52 4A+4M allocation fix + TSV data

## Priority stack
```
priority:1  #54  A* pathfinding / navigation efficiency  <- NEW
priority:2  #41  RL policy training                      <- BLOCKED (needs GPU)
priority:3  #53  Multi-agent cooperation paper
priority:3  #50  Per-agent alignment efficiency           <- target met
priority:3  #27  Andre Von Huck / A*
priority:3  #26  shweta policy
priority:3  #31  change_vibe actions
priority:3  #12-#23  various speculative
```

## Open questions for next director

1. **v52 stability**: With only 23 matches, the score may shift. Monitor — if it drops below 34, investigate whether the match quality was lucky.

2. **A* implementation**: Issue #54 is the next high-leverage experiment. The current BFS is O(V+E) per call with no heuristic — A* with Manhattan distance would focus search toward the goal and reduce wasted exploration. Key files: `aligner_agent.py:_bfs_first_direction`, `llm_skills.py:_bfs_first_direction`.

3. **Allocation lesson for future submissions**: NEVER submit with a different allocation than 4A+4M without online validation first. The offline→online correlation for allocation is INVERTED — what's best offline (3A+5M) is worst online.

4. **Branch cleanup candidates**:
   - `amazing-meitner-gp8Vw` (partially merged — code from v52 only)
   - `amazing-meitner-b3onP` (diagnostic work, subsumed by gp8Vw)
   - `amazing-meitner-ZmdFf` (merged in session 20)
   - All `autoresearch/*` branches (ancient, sessions 1-8)
   - All `pr/*` and `revert/*` branches (stale)

5. **v55 defend queue**: Second best at 34.31. The idea has merit but the implementation may be too aggressive. A future researcher could try a softer version — defend only when ALL nearby junctions are aligned AND heart queue is full, rather than any one condition.

6. **Submit cadence**: v52 was submitted 2026-04-29 06:23. Give it at least 40-50 matches before deciding on a new submission. No point submitting v53-v58 — they all regressed.
