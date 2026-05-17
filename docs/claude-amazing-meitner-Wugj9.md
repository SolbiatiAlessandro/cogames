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

## 2026-05-17 18:20 UTC: Arena training ALSO fails — no alignment after 80 epochs

Evaluated arena-trained checkpoints (e30-e80) on both arena and competition map.
Results: ALL 0.500 (arena baseline) or 0.050 (competition baseline), ZERO junction alignment.

Detailed stats show agents explore (cell.visited up to 49K), pick up random gear (solar,
carbon, aligner, miner), but NEVER withdraw hearts and NEVER align junctions.

Root cause: training without simplifications (start-aligner, start-heart, flat-map, no-clips)
requires agents to discover a 3-step sequence through random exploration:
1. Pick up aligner gear from station
2. Withdraw heart from hub
3. Navigate to junction and align

This is too sparse for RL to discover from scratch.

## 2026-05-17 18:25 UTC: KEY DISCOVERY — Original Phase 1 used --start-aligner --start-heart

Re-read previous session's (claude/amazing-meitner-9HeB9) experiment log. Phase 1 was
"minimal_align" config: --start-aligner --start-heart --flat-map --no-clips.

This eliminates the discovery problem: agents START with gear, just need to navigate to
junctions. Much easier for random exploration to stumble upon alignment.

The full successful pipeline was:
1. Phase 1: minimal_align on arena (flat, no clips, start with gear)
2. Phase 2a: natural terrain on competition map from P1 weights
3. Phase 2b (compmap_v1): max_dist=6 on competition map
4. longep: 2000-step episodes from compmap_v1 (entropy breakthrough)
5. sprint_compmap → midep_compmap → midep_tightclip (best model)

Restarted training with correct minimal_align config. Training running.

## 2026-05-17 18:40 UTC: MODEL IS LEARNING — eval was wrong

Evaluated minimal_p1 e60 on MATCHING environment (flat arena, start-gear, max_dist=6):

| Steps | Avg reward | Peak reward | Junctions aligned |
|-------|-----------|-------------|-------------------|
| 500   | 0.940     | 1.393       | 1-2/episode       |
| 1000  | 1.649     | 1.979       | 0-1/episode       |
| 2000  | 4.549     | 7.715       | 1-3/episode       |

Previous evals showed 0.050/0.500 because they evaluated on DIFFERENT environments
(non-flat arena without start-gear, or competition map). The model IS learning alignment.

The peak of 7.72 @2000 steps matches previous session's Phase 1 peak of 7.78!

Resumed training from e60 weights for continued improvement.

Plan:
1. Let Phase 1 train to e80+ equivalent
2. Start Phase 2: warm-start on competition map (natural terrain, no clips)
3. Phase 3: full competition map with clips
4. Eval at each stage

## 2026-05-17 18:50 UTC: Phase 2 started on competition map

Resumed Phase 1 for 20 more epochs (e60→e80 equivalent). Then started Phase 2:
- Competition map (cogsguard_machina_1.basic), natural terrain
- max_dist=6, no clips, NO start-gear (full pipeline learning)
- Warm-start from Phase 1 e80 equivalent checkpoint
- clip_coef=0.1, ent 0.04→0.01, boost_aligner=5.0
- 1000-step episodes, 4 cogs, 16 envs

The model transitions from simplified (flat map, start with gear) to realistic
(natural terrain, must find gear). Expect initial U-curve degradation then recovery.
