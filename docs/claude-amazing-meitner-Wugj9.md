# Experiment Log: claude-amazing-meitner-Wugj9
## Issue #75: RL Curriculum Training — Phase 2+3 on Competition Map

## 2026-05-17 17:10 UTC: Autoresearch starting

Plan: Continue RL curriculum training from issue #75. Previous sessions achieved:
- tightclip_e80: 0.123 avg @500 steps (best short-episode)
- p2lr_e20: 1.124 avg @10K (best competition length)
- withclips_e10: 1.053 avg @10K (corrected from initial 1.371)
- All models plateau at ~1.05 avg @10K steps

Key findings from prior work:
- clip_coef=0.1 solves entropy collapse (the "tightclip" discovery)
- 1000-step episodes are the sweet spot for training
- Competition map training is essential (arena doesn't transfer)
- Phase 2 (max_dist=10) is the curriculum sweet spot
- temp=0.7 at eval time gives free 15% improvement

No checkpoints available in fresh environment — training from scratch.

My plan:
1. Start Phase 1 training from scratch with proven best config (tightclip, competition map, 1000-step episodes)
2. Attempt tournament submission with Softmax token
3. Try new ideas: mixed-distance training, larger obs window, 8-agent training

## 2026-05-17 17:15 UTC: Starting Phase 1 baseline training

Training from scratch with optimal hyperparameters:
- clip_coef=0.1, ent_annealing 0.04→0.01 over 50%
- boost_aligner=5.0, max_dist=6
- 1000-step episodes, competition map
- 8 cogs (full team), 16 envs (CPU-friendly)

## 2026-05-17 17:25 UTC: Training in progress, auth blocker identified

Training running at ~2.5K SPS. Epoch 109 reached, entropy at 1.22 (still healthy).
Checkpoints saved every 5 epochs up to epoch 70 so far.

**Auth blocker**: Softmax token works for read (leaderboard shows us at #5 with 41.85)
but fails for write operations (upload, my policies). Browser-based OAuth2 required
but can't be done from this environment. Tournament submission remains blocked.

## 2026-05-17 17:30 UTC: Evaluating early checkpoints

Running eval_rl.py on epoch 60 checkpoint at 500 steps. Eval competing with
training for CPU resources — runs slowly.
