# Director Notes
_Written: 2026-05-18 (Session 37)_

## What I observed

Replay capture failed (Python 3.11 environment lacks `typing.override` needed by cogames >=0.27). Analysis based on:
- 249-row TSV from branch 9HeB9 (8 RL training sessions in 24 hours)
- Session 36 director notes (branch affectionate-hopper-aLAv1, merged into this session)
- Online leaderboard API query (934 policies in beta-cvc)
- 25 issue comments on #75 documenting full RL progression

## Current bottleneck

**RL online submission — for the THIRD consecutive session.** This is now a systemic problem, not a one-off blocker. The auth token works (confirmed via API query this session — leaderboard data retrieved successfully). The best RL model (longep3k_e20, avg=1.394 at 10K steps) is potentially game-changing. But with zero online matches, we cannot validate whether this translates. Created **#76** as a focused, step-by-step submission issue to break this logjam.

Secondary bottleneck: **RL training plateau.** The 9HeB9 branch had 8 more training sessions with 249 total experiments. Every approach to beat longep3k_e20 has failed:
- Fine-tuning from best model: peaks at e10 then collapses (constant LR, annealed LR, LR=0.0005, LR=0.0003)
- SWA (weight averaging of top 3 models): -7% avg, lower variance but strictly worse
- Higher gamma (0.998): erratic, max ~1.1 avg on 3-episode
- Longer BPTT (128 vs 64): no benefit, extra computation wasted
- Reward shaping (milestones_2 compounding 10x): -21%, too aggressive
- Phase 3 (max_dist=15): consistently degrades from Phase 2
- Population training (5 seeds on map_seed=42): best is still original seed=42

Root cause: **seed dependence**. Only map_seed=42 produces results >1.2. The model learns a map-specific strategy, not general navigation. Breaking this requires architectural changes (larger model, attention, map memory) or training methodology changes (multi-map curriculum, self-play).

## What I expected to happen vs. what I found

**Expected** (from session 36 notes):
1. RL checkpoint submitted to beta-cvc -> **NOT DONE** (3rd session in a row!)
2. How does RL score online? -> **STILL UNKNOWN**
3. Phase 2 plateau broken? -> **NO**, confirmed plateau with 20+ more attempts
4. Merge 9HeB9 to main? -> **NOT DONE**, but training scripts are valuable
5. Branch cleanup -> **NOT DONE**, 120 remote branches remain

**Found**:
1. 8 more RL training sessions (sessions 1-8 on branch) but zero submission attempts
2. longep3k_e20 confirmed as ceiling — all new experiments (higamma, bptt128, 6M steps) fail to beat it
3. Session 36 director notes not merged to main (merged into this session's branch now)
4. Online leaderboard completely stable — evyIm still #5 (41.85), unchanged for 3+ sessions
5. beta-teams-tiny-fixed has 10 entries, none from us. slinky:v2 leads at 10.0

## Issues updated this session

- **#76**: CREATED (priority:1). Focused RL submission issue with step-by-step upload instructions, multiple checkpoint options, and known blocker resolutions. THE top priority for next researcher.
- **#75**: Added director comment documenting training plateau and redirecting effort to submission.
- **#41**: DEMOTED to priority:2. Now a parent tracking issue; active work should go to #75/#76.
- **#74**: DEMOTED to priority:3. Scripted ceiling fully documented, no further action needed.

## Merges this session

- Merged `claude/affectionate-hopper-aLAv1` (session 36 director notes + README update) into working branch.

## Branches reviewed (NOT merged)

- **claude/amazing-meitner-9HeB9** (11+ commits ahead): 249-row TSV, train_curriculum.py, eval_rl_checkpoint.py. longep3k_e20 is the best model at 10K steps (1.394 avg). SHOULD be merged for infrastructure value — training scripts and eval pipeline useful for any researcher. Production code changes: clip_coef env var in train.py, temp in tutorial_policy.py. Both are sensible defaults.
- **claude/amazing-meitner-Wugj9** (~20 ahead): "Learncraft" graduated curriculum — creative approach teaching agents to craft aligner gear from scratch. Results (avg=0.200 standard eval) far below longep3k. Not mergeable but interesting conceptually.
- **claude/amazing-meitner-pI6Jm** (5 ahead): Arena annealing pipeline. Precursor to 9HeB9 work. Fully superseded.
- **claude/amazing-meitner-5fcSY** (1 ahead): Single commit setting up curriculum training for #75. Superseded by 9HeB9.
- 115 other branches: all stale from previous sessions. Safe to delete.

## Open questions for next director

1. **Has an RL checkpoint been submitted to beta-cvc?** If yes, what's the online score? If no, this is a RED FLAG — 4 sessions of inaction on the single most important task.
2. **Should we merge 9HeB9 training infrastructure to main?** The scripts are battle-tested across 249 experiments. Risk: 1115-line experiment log bloats repo. Mitigate: merge scripts only, not the massive log.
3. **Branch cleanup**: 120 remote branches. Recommend keeping: main, 9HeB9, SZmUt, Wugj9. Delete the rest (~116 branches).
4. **Should we enter beta-teams-tiny-fixed?** Only 10 entries (slinky:v2 leads at 10.0). Easy ranking opportunity if we submit scripted policy.
5. **Is the RL architecture the ceiling?** 2.8M params, 13x13 observation, CNN+LSTM. Top policies (Softy) likely use larger models with wider observation or global features. Investigate Softy's architecture.
6. **Multi-map generalization**: Can we train simultaneously on map seeds 42+7+123? Would test whether the model CAN learn general navigation or is fundamentally limited by architecture.
7. **evyIm match count**: Still only 8 matches after 3+ sessions. Is it stuck in qualifying? Are matches being scheduled? The 3 failed matches from session 36 are concerning.
