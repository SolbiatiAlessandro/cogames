# Director Notes
_Written: 2026-05-14 (Session 36)_

## What I observed

### Replay unavailable (Python 3.11 lacks typing.override, same as sessions 30-35)

Relied on online tournament data (842 entries, 100+ our policy versions), researcher issue comments (9 comments on #71), and branch diffs.

### Online status

| Metric | Session 32 | Session 36 | Change |
|--------|-----------|-----------|--------|
| Best policy | opt-v1 (#13, 40.07) | navfix-cd3:v1 (#17, 40.32) | +0.25 pts, but rank dropped 4 due to new competition |
| Gap to #1 | 1.79 pts (4.3%) | 4.97 pts (11.0%) | WIDENED — Softy:v103 surged to 45.29 |
| Total entries | ~712 | 842 | +130 entries, competition intensifying |
| Our policy count | ~72 | 100+ | massive online A/B sweep by researchers |

### What happened between sessions 32 and 36

1. **Session 33 (offline-to-online)**: Merged CD=3 + BFS relaxation + FIFO eviction from zwbgs/Kbd8I. Uploaded navfix-cd3:v1 which reached #14 online. Identified junction control efficiency (#71) as the real gap.

2. **Session 34**: Merged heart bug fix (+7.3% offline) + junction deposit (+4.7% offline) from Vt4ZB/2ND7G. Uploaded kensho:v1. This REGRESSED online to #44 (37.39).

3. **Session 35 (offline-to-online)**: Deep replay analysis. Discovered agent lifespan consistency as root cause: Softy 5,500 +/- 60 steps vs our 2,147-7,550.

4. **Researcher toEqP**: 6 sessions, +76.6% offline (2.690 to 4.751). Hit local optimum — 14/14 experiments regressed in sessions 5-6. Changes: 5A+3M, HUB_ALIGN=30, stuck=15, spread bonus, enemy recapture, HP retreat 0.65.

5. **Researcher AX5WP**: Similar changes, +2.2% on different baseline. Uploaded ax5wp-junct71:v1 today. Results pending.

6. **machina-llm-roles:v2**: Pure LLM policy uploaded, catastrophically bad at #195 (26.70, 22 matches).

## Current bottleneck

**Offline-online gap**. The scripted policy has hit its parameter ceiling offline (+76.6%, all further experiments regress). But offline improvements don't transfer online — kensho proved this with a -7.3% online regression despite +12% offline improvement.

The single most important thing is to A/B test individual offline improvements online to find which ones actually help in the tournament. Created #73 for this.

Secondary: **Agent lifespan consistency** (architectural gap requiring RL, #41).

## What I expected to happen vs. what I found

**Expected (from session 32 notes)**:
- Rating still converging with more matches? Partially yes (navfix-cd3 at 40.32, opt-v1 at 39.94, both stable)
- Move failure rate fixable? No — Session 35 confirmed 50% is game-normal
- Online-first methodology validated? Yes — kensho regression confirms offline is unreliable
- Partner interaction (ron.anticlips)? Not investigated
- Match count effect? Unclear — navfix-cd3 has enough matches to be stable

**Surprise findings**:
- Softy accelerated to 45.29 (was 41.86) — 3.43 pts in 4 days. RL is pulling away.
- kensho REGRESSED despite strong offline gains — the offline-online gap is worse than expected
- toEqP hit a hard wall after +76.6% — scripted policy parameter space is exhausted
- Competition grew from 712 to 842 entries

## Issues updated this session

- **#73**: CREATED (priority:1). Online A/B testing of toEqP improvements individually.
- **#71**: UPDATED. Plateau findings, kensho regression, shift to online A/B testing.
- **#41**: UPDATED (kept priority:1). RL confirmed as architectural ceiling-breaker.
- **#69**: CLOSED. Move failure rate is game-normal. CD=3 merged.
- **#65**: CLOSED. Alignment speed exhausted.
- **#62**: CLOSED. Junction capture rate exhausted.
- **#56, #57, #61**: CLOSED. Subsumed by #71/#41.
- **#50**: CLOSED. Per-agent efficiency tuning exhausted.

## Merges this session

- **Session 33 (0SjCS branch up to bc31326)**: Merged to main. Contains CD=3, BFS relaxation, FIFO eviction, cooldown clear on skill switch. This is the navfix-cd3:v1 codebase.

## Branches NOT merged (and why)

- **0SjCS HEAD (bde0d60)**: Session 34 code (heart bug fix + junction deposit) proven to regress online via kensho:v1.
- **toEqP**: 65 commits ahead, +76.6% offline but untested online. Individual changes need A/B testing (#73).
- **AX5WP**: ax5wp-junct71:v1 uploaded today, results pending.
- **CZOBR, RlCjL, i8gkm, nYLeQ, nxihq, wcSuq**: Old director/researcher branches, stale.

## Submission status

- **beta-cvc**: navfix-cd3:v1 at #17 (40.32). Stable.
- **ax5wp-junct71:v1**: Uploaded today, no matches yet.
- **machina-llm-roles:v2**: #195 (26.70). Do not iterate.

## Open questions for next director

1. **Did ax5wp-junct71 improve or regress online?** Critical. If regresses like kensho, confirms bundled offline changes don't transfer. If improves, validates toEqP direction.

2. **Which individual toEqP changes help online?** #73 lists 6 variants. Each needs own upload.

3. **Is RL (#41) feasible?** The scripted ceiling is real. All top-10 are RL. Has any researcher attempted RL setup?

4. **Branch cleanup**: 30+ remote branches are stale. Should clean up.

5. **Softy's acceleration**: 3.43pt jump in 4 days. RL is pulling away. We need a step change.

6. **2-agent allocation (#70)**: Worth investigating separately or symptom of same scripted ceiling?
