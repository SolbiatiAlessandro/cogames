# Director Notes
_Written: 2026-04-13 (Session 7, offline-to-online)_

## Offline observations

Three autoresearch branches ran experiments since session 6. All three merged this session:

### Priority branch (claude/autoresearch-priority-issue-dAc9K) — MERGED
- Best config: 3A5M (3 aligners, 5 scripted miners), stuck_threshold=28, hazard-free BFS
- 6-seed average: 4.83 total (0.604/agent) at 1k steps — +40% over baseline
- Best single seed: 7.96 total (seed 47) = 0.996/agent — stretch target exceeded
- Key insight: hazard-free BFS in gear_up/get_heart/align_neutral eliminates gear contamination
- 4/6 seeds above primary 4.0 target; 2 seeds (45, 46) structurally limited

### Issue #34 Heart Pipeline (claude/amazing-meitner-cUcXZ) — MERGED
- v7 best at 1k: 0.84/agent (+110% over baseline 0.40/agent)
- v7 at 10k: 1.74/agent (marginal +8% over 1.61 baseline)
- Fixes: persistent aligner retry, hub heart filter, miner HP emergency deposit
- 12 variants tested; v7 is clear winner
- **At 10k, the fix decays** — team collapses, 2/4 aligners stuck, miner deaths

### Issue #35 Move Failure (claude/amazing-meitner-ahBE5) — MERGED
- Perpendicular dodge + smart greedy v3: 0.97/agent at 1k (+33%)
- 10k validation: 88.3% move success (vs 79% baseline), 78% fewer failures
- Merge conflict in `_greedy_move_toward_abs` resolved: combined obstacle-aware sorting with hazard avoidance

## Online observations

### Leaderboard (2026-04-13)
- **#288/359**: `lessandro-fast-llm-v1:v1` score 3.12 (unchanged from session 6)
- **#302/359**: `cross_role_full_10s_v8:v1` score 2.71 (slightly down)
- Top-1: `dinky:v27` at 27.40 (was 27.63 — more entries dilute scores)
- Total: 359 entries (up from 344)
- **No new submissions since session 6** — all improvements are offline-only

### Replay analysis (4 matches deep-dived)

| Match | Score | Our agents | Partner | Key finding |
|-------|-------|-----------|---------|-------------|
| vs scissors_v67 | 6.97 | 2 active, survived to 7759-9769 | scissors died 190-628 | Best: 88 junctions, 18.6 hearts/agent, 95.9% move success |
| vs shweta.smart-v77 | 2.86 | 2 active, died 7889-8207 | shweta died 4177-6253 | 15 junctions, 45% move failure, everyone died |
| vs shweta-v50 | 0.36 | 5 agents, ALL died 2856-5793 | shweta 1 survived | Catastrophic: 0 carbon deposited, 0.75 hearts/agent |
| vs dinky.eercln.s2 | 0.92 | 2 active, died 7267-7815 | dinky variant (0 moves) | Only 4 junctions despite no opposition; ceiling visible |

### Critical finding: cooperative scoring
All 8 agents share the same reward (team score). We only contribute 2 agents per match (partner has 6). Score depends heavily on partner quality:
- Weak partner (scissors/dinky.s2 doing nothing): we score 0.92-6.97
- Active partner (shweta): we score 0.36-2.86
- Range is 20x within our own matches

### Answering session 6 open questions
1. **Heart withdrawal mechanics**: Confirmed: `heart.withdrawn: 5` tracks hub hearts. dinky gets 56 hearts/agent via a different mechanism — likely picking up crafted hearts by stepping on hub, not via explicit withdraw. Our agents avoid the hub after hub_depleted.
2. **Action_id sparsity**: Confirmed delta-encoded. Our agents with 7759 action_id entries made 9588 actual moves. The 148-entry agents from session 6 were likely nearly-dead.
3. **Online map differences**: Yes, maps vary per match (junction counts differ). This explains some score variance.
4. **v9 improvements**: Hazard-avoidance is now in main via the priority branch merge. Miner nav improvements partially via the move failure branch.
5. **Cooperative failure rate**: Confirmed congestion-driven. With dead partners (0 active partner agents): 95.9% success. With active partners: 55%. The fewer agents moving, the less congestion.

## Offline→Online gap

### Current state
1. **Offline ceiling**: 0.996/agent (1k), 1.74/agent (10k)
2. **Online ranking**: #288/359, score 3.12
3. **Gap is closing slowly**: session 6 gap was 5.7x to dinky, now 3.9x in best match

### What explains the gap
1. **Submission lag (PRIMARY)**: Three branches improved offline by 33-110% but nothing was uploaded. The currently submitted policy predates ALL improvements.
2. **Agent mortality**: ALL agents die before step 10,000 in every match. `heart.withdrawn=5` in EVERY replay. Make_heart products are never collected.
3. **Heart pipeline decay at 10k**: The v7 fix works at 1k (+110%) but only gives +8% at 10k. The mechanism breaks down over longer episodes.
4. **2-agent contribution**: We only get 2 agents in cooperative matches, so our individual agent quality is amplified or diluted by 6 partner agents.

### Bottleneck: online (agent mortality) > offline (policy quality)
The offline improvements are significant and real, but they don't translate to online because:
- Online runs 10k steps; agents die at 5-8k
- Without surviving agents, junction-held-ticks plateau
- The heart pipeline fix barely helps at 10k

## Issues updated this session
- **#28**: CLOSED as completed (qualifying crash fixed, competition pool active)
- **#34**: Commented with online evidence; branch merged; kept priority:1 in-progress
- **#35**: Commented with online evidence; branch merged; moved to priority:2 (partially resolved)
- **#36** (NEW): Agent mortality crisis — priority:1 — the #1 online gap
- **#30**: Moved to priority:3 (subsumed by #36)

## Priority stack
```
priority:1  #36  Agent Mortality (NEW)                    <- SPAWN NEXT (highest leverage)
priority:1  #34  Heart Pipeline (in-progress, merged)     <- SPAWN NEXT (feeds into #36)
priority:1  #29  10k Step Eval Alignment                  <- after #36/#34
priority:2  #35  Move Failure Rate (in-progress, merged)  <- partially resolved (88.3%)
priority:2  #25  8-Agent Scaling
priority:2  #24  Balanced Mining Strategy
priority:2  #27  Andre Von Huck suggestions
priority:2  #26  shweta policy analysis
priority:2  #20  Coordinated Exploration
priority:2  #19  LLM Code Gen | #17 LLM Skill Validation
priority:2  #21  Intrinsic Motivation | #11 Active Inference | #10 Role Tuning
priority:3  #30  8-Agent Self-Play (subsumed by #36)
priority:3  #31  change_vibe (non-issue)
priority:3  #32  Partner robustness | #12 Gear Acquisition | #23 Meta-Learning | #22 Social Influence
```

## Open questions for next director

1. **Submit the merged code?** Three branches were merged but no new policy uploaded. The merged code combines hazard-free BFS + heart pipeline + move failure fixes. Should be submitted with config: `class=cross_role,kw.num_aligners=3,kw.num_scouts=0,kw.stuck_threshold=28,kw.llm_timeout_s=10`. Estimated online improvement: 30-50% based on offline gains.

2. **Why do agents die at 7-8k steps?** Hearts run out at ~step 500 (5 initial). Make_heart crafts new ones but agents never collect. Is the hub_depleted flag blocking? Do agents need an explicit "check hub for crafted hearts" behavior?

3. **Cooperative 2-agent limit**: We only contribute 2 agents per match. Is there a way to increase this? Or should we optimize the 2 agents to be maximally self-sufficient?

4. **Should we submit the priority branch config (3A5M stuck=28) or the heart pipeline config (4A4M v7)?** The priority branch has higher 1k reward but wasn't validated at 10k. The heart pipeline has lower 1k reward but was validated at 10k (1.74). Need a 10k run of the combined merged code.

5. **Move failure correlation with partner count**: Our 95.9% success rate with dead partners vs 55% with active partners confirms congestion is the main driver. Can we detect when our agents are bumping into allies vs walls?
