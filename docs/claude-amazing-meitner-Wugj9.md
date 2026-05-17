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

## 2026-05-17 17:35 UTC: CRITICAL FINDING — 8-agent training produces broken model

Evaluated epoch 80 (trained with 8 agents):
- @500 steps: avg=0.065, peak=0.075 (4/5 episodes dead at 0.050)
- @1000 steps: avg=0.100 (all episodes at base survival, zero junction alignment)
- cogs/aligned.junction.held = 0.0 — model NEVER aligns junctions
- aligner.gained = 1.625 (picks up gear) but heart.gained = 0.125 (never withdraws hearts)

Previous session's tightclip_e80 (trained with 4 agents): avg=0.123 @500, avg=0.375 @1000

Root cause: Training with 8 agents on competition map prevents learning the alignment pipeline.
With 8 agents, there's too much congestion at hub, reward signal is too sparse per agent.

Fix: Restarted training with 4 agents (matching previous session's successful config).

## 2026-05-17 17:38 UTC: Restarted Phase 1 training with 4 agents

Config: Same tightclip config but --cogs 4 instead of 8.
This matches the previous session's successful training pipeline.

## 2026-05-17 18:00 UTC: CRITICAL — From-scratch competition map training TOTAL FAILURE

Evaluated all 4-agent checkpoints (e40, e60, e80, e100, e105):
- ALL produce 0.050 @500 steps (pure survival)
- ALL produce 0.100 @1000 steps (pure survival)
- ZERO junction alignment across 25+ episodes
- Model learns hub interactions (heart withdrawal, aligner pickup) but never navigates to junctions

Root cause: `patch_junction_distance(max_dist=6)` doesn't control junction PLACEMENT on competition
maps. The `EnsureHubReachableJunctionConfig` only guarantees at least one junction reachable
within max_distance, but the main junction distribution (Poisson across 88×88 map) still scatters
junctions far from hub. The reward signal for junction alignment is too sparse for random
exploration to discover.

Previous sessions' success came from the arena-first pipeline:
1. Train on arena (where close junctions ARE the only junctions) — agent learns alignment
2. Warm-start on competition map — agent already knows alignment, just adapts navigation

## 2026-05-17 18:05 UTC: Started Phase 1 arena training

Pivoting to arena-first approach. Config:
- mission: cogsguard_arena.basic (NOT competition map)
- max_dist=6, clip_coef=0.1, ent 0.04→0.01, boost_aligner=5.0
- 1000-step episodes, 4 cogs, 16 envs
- 4M steps total, checkpoint every 5 epochs
- Patching confirmed working: "Patched MachinaArena.get_children max_distance to 6"

Plan: Train arena to ~e60-80, eval, then warm-start Phase 2 on competition map.
