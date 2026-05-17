# Director Notes
_Written: 2026-05-17 (Session 36, offline-to-online)_

## Offline observations

### Scripted policy
- **Unchanged since session 34**. evyIm-73a-stuck15 remains the best scripted at 0.18/agent @500 steps.
- No new scripted experiments since session 35. 60+ A/B variants exhausted (#74).
- 3.282 total reward @3000 steps (8-agent, contamination fix) remains offline ceiling.

### RL training (branches SZmUt and 9HeB9)
- **Phase 2 curriculum (max_dist=10) is the current best approach**:
  - e15: 0.109 avg @500s (reliable, 10-episode), 0.271 peak @500s
  - e20: 0.394 avg @1000s, 0.503 peak @1000s — **2x scripted**
  - e30: 0.754 peak @1000s — ALL-TIME BEST at 1000 steps
- **Tightclip (clip_coef=0.1) was the key discovery**: solves entropy collapse, enables training past epoch 50
- **midep_compmap e50 beats scripted 0.18 target** at 500 steps
- **2000-step episodes solve entropy issues** — longep breakthrough
- **What FAILED**: Phase 3 (max_dist=15), ultrasprint (300-step episodes), natmap (natural map sprint), hiboost (boost_aligner=15) — all degrade from Phase 2 best
- **Training has plateaued at Phase 2**: Phase 2 e15 remains best reliable checkpoint, e20-e30 overfit to 1000+ steps but degrade at 500
- TSV: 109 experiment rows on 9HeB9 branch

## Online observations

### Leaderboard (beta-cvc, 934 policies total)
- **#5**: evyIm-73a-stuck15:v1 — score 41.85, stddev 7.06, **only 8 matches** (same as session 35)
- **#1**: Softy:v103 — score 45.29, stddev 16.53, 20 matches
- **Gap to #1**: 3.44 points (7.6%)
- **New**: Gryffindor:v11 entered #12 (40.82, 27 matches)
- **159 of our policies** in the tournament (from A/B testing rounds)
- Two active seasons: beta-cvc (in_progress), beta-teams-tiny-fixed (in_progress)
- 3 failed matches for evyIm — against ron.calib, ron.massive, osprey. Match failures (policy crash or opponent crash).

### Replay analysis: evyIm-73a-stuck15

**Low-scoring match (21.44, vs ron.anticlips.v4.baseline.b:v2)**:
- 2 evyIm agents + 6 ron agents on same team (Cogs)
- Ron "anticlips" agents barely active (600-1500 steps out of 10k) — disruption strategy, not productive
- Our agent_0: 6255 steps active, agent_1: 2310 steps active
- Clips dominated: 482k junction-held vs Cogs 214k
- avg max_steps_without_motion: 3961 — massive stuck periods
- Zero vibe transitions in action log (expected — gear via station stepping)

**High-scoring match (46.60, vs evyIm-73k-patience10:v1)**:
- All 8 agents are our policies (6 evyIm + 2 patience10)
- Agent lifespan: 2143-6976 steps (wide variance)
- 13.375 deaths per agent! Agents dying and respawning repeatedly
- max_steps_without_motion: 75.5 (much better)
- Clips STILL held more junction-time (564k vs 466k Cogs) — even in our best game we're outpaced by NPC Clips
- 107 junctions gained across team

**Key insight**: Score variance (21-46) is dominated by **partner quality**, not individual policy quality. When all agents are ours, we score 40-46. When paired with anticlips/weak partners, 21-25.

## Offline-to-Online gap

1. **RL submission is the #1 gap**: RL beats scripted at 1000+ steps offline but has ZERO online matches. Cannot validate the offline-to-online translation for RL without submitting.
2. **Variance structure differs**: Our scripted stddev (7.06) vs Softy's RL stddev (16.53). Softy's high variance means higher peaks (p95=57.5 vs our 46.6). RL should unlock higher variance/ceiling.
3. **Partner dependency**: Cooperative format means score depends on teammate. Top-scoring matches are always against our own policies (inflated). Real-opponent matches score 21-35. This suggests our TRUE competitive strength is lower than #5.
4. **10k steps online**: RL improves with longer horizons (0.109@500s → 0.394@1000s → 0.954@2000s). Online runs 10k steps. The RL advantage should be enormous at online timescales.

## Current bottleneck

**RL online submission and validation.** The offline RL work has exceeded scripted at 1000+ steps. The next step is submitting the best Phase 2 checkpoint to beta-cvc and seeing where it ranks. Without this, we're flying blind — all the offline improvements could be meaningless if they don't transfer online.

Secondary bottleneck: **RL training plateau at Phase 2.** Phase 3 (max_dist=15) failed. Need a new approach to train RL on full competition distance.

## Issues updated this session

- **#75**: Updated with comprehensive RL results from 9HeB9 branch. Phase 2 exceeds scripted. Phase 3 failed. Submission is the priority.
- **#41**: Updated with latest breakthrough — RL exceeds scripted at 1000+ steps.
- No priority changes needed — existing priorities are correct.

## Merges this session

None. RL branches (SZmUt, 9HeB9) have valuable results and scripts but policy code changes are minimal (1 env var in train.py). The training infrastructure should be merged once RL is validated online.

## Branches reviewed (NOT merged)

- **claude/amazing-meitner-9HeB9** (today, 11 ahead): Latest RL curriculum work. Phase 2 best reliable=0.109@500s, Phase 3 FAILED. 109-row TSV. train.py change is trivial (clip_coef env var). Worth merging for infrastructure after RL online validation.
- **claude/amazing-meitner-SZmUt** (7 ahead): Earlier curriculum work. Phase 1a peak 7.78/agent (simplified). Phase 2a transfer working. Foundation for 9HeB9's work.
- 100+ other remote branches: all stale from previous sessions. Safe to prune.

## Open questions for next director

1. **Has the RL checkpoint been submitted to beta-cvc?** This is THE priority. Token is working (used this session to query API).
2. **How does RL score online?** If Phase2 e15 scores 35+ online, it validates the offline work. If it scores <30, the gap is larger than expected.
3. **Can Phase 2 plateau be broken?** Phase 3 failed. Options: longer training (more epochs), larger model, reward shaping changes, self-play.
4. **Should we merge 9HeB9 to main?** The training scripts and TSV results are valuable. Only 1 trivial production code change.
5. **Branch cleanup**: 100+ remote branches. All stale except SZmUt and 9HeB9.
6. **evyIm match count**: Still only 8 matches. More matches will either confirm #5 or reveal it was lucky. The 3 failed matches are concerning.
7. **beta-teams-tiny-fixed season**: Active but no entries from us. Worth checking if it's easier to rank in.
8. **Gryffindor:v11**: New entrant at #12 (40.82). Is this RL or scripted? What's their approach?
