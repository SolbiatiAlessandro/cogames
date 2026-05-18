# Experiment Log: claude-amazing-meitner-pI6Jm

## Issue: #75 — RL Curriculum Training Phase 2+3 on Competition Map

## 2026-05-18 05:20 UTC: autoresearch starting

**Plan**: Continue RL curriculum training from issue #75. Previous sessions achieved:
- Best model: longep3k_e20 at avg=1.394 @10K steps (seed-dependent, seed=42 only)
- seed=123 only gets ~1.07 — the 1.394 is a lucky optimization trajectory
- Key finding: 3000-step training episodes are THE critical hyperparameter
- Active direction: reward shaping via milestones_2 compounding factor

**My hypothesis**: The seed dependence comes from the reward signal being too weak relative to the alive reward (~1.0/agent). By increasing the milestones_2 compounding factor (currently 5.0), we can amplify the alignment reward signal and get more robust convergence across seeds.

**Experiments planned**:
1. Phase 1 baseline: arena, 4 cogs, ent=0.04, clip=0.1, m2_factor=5 (reproduce baseline)
2. Phase 1 with m2_factor=25 (5x amplification)
3. Phase 1 with m2_factor=50 (10x amplification)
4. Best Phase 1 → Phase 2 (3000-step episodes on competition map)
5. Compare seeds 42, 123, 7 for robustness

**Container setup**: Python 3.12 venv, CPU-only (4 cores, 15GB RAM), ~2.5K SPS expected.

## 2026-05-18 05:20 UTC: starting Phase 1 baseline training

First attempt with fixed ent_coef=0.04 — entropy stayed at ~1.60 (near max for 5-action space = ln(5)≈1.609). The model was essentially random. Killed after 141 pufferl epochs.

**Key lesson**: Fixed ent_coef doesn't work for this action space. Must use entropy annealing (successive training runs with decreasing ent_coef).

## 2026-05-18 05:30 UTC: restarting with proper entropy annealing

Using the "proven approach" from previous sessions:
- Stage 1a: ent=0.08, 30 epochs (exploration, near-random)
- Stage 1b: ent=0.02, 50 epochs (learning, targeted behavior)  
- Stage 1c: ent=0.01, 30 epochs (exploitation, polished)

Each stage warm-starts from the previous stage's best checkpoint. clip_coef=0.1 (tight clipping for Phase 1 convergence).

Running now with m2_factor=5 (baseline). ETA ~47min for full Phase 1 pipeline.

Early signs: junction.held = 258 and 541 appearing at epoch 14-16 with ent=0.08. Good sign of exploration finding alignment behavior.

## 2026-05-18 05:46 UTC: Stage 1a complete

Stage 1a (ent=0.08, 30 pufferl-epochs, 1.92M steps) completed in 17.1 min at ~2500 SPS.
- Best checkpoint: `train_dir_p1_anneal_m2x5_s42/stage1a/177908215231/model_000469.pt`
- 469 pufferl gradient steps (30 "epochs" at ~16 gradsteps each)
- junction.held peaked at 2912, but mostly sparse (near-random exploration phase)
- Model has found alignment behavior but not reliably

Stage 1b (ent=0.02, 50 epochs, 3.2M steps) now running. This is where policy specialization begins.

## 2026-05-18 05:47 UTC: Stage 1b training (ent=0.02)

Target: concentrate learned alignment behavior. The ent=0.02 forces the model to commit to a policy rather than staying near-uniform random. Expected to see junction.held values become more consistent (less variance, higher mean).

## 2026-05-18 05:55 UTC: PLAN CHANGE — map_seed=42 is the key (Session 6 finding)

Read all 23 comments on issue #75. Critical finding from Session 6:
- **map_seed=42 is what makes training succeed** — the MAP LAYOUT, not optimizer seed, determines success
- map42 + seed7 → avg=1.283; map42 + seed123 → avg=1.197 (both work!)
- Without map42: seed7 → 1.000, seed123 → 1.072 (both fail)
- **milestones_2:10 already FAILED** (avg=1.103 vs 1.394 baseline) — m2x25 would be even worse

New experiment plan:
1. map42 + seed42 + m2x5 (baseline reproduction, expect ~1.39)
2. map42 + seed123 + m2x5 (KEY: does fixed map fix bad seed?)
3. map42 + seed7 + m2x5 (third seed robustness)
4. NO map_seed + seed123 + m2x5 (control: confirm bad seed fails without fix)

Added --map-seed CLI arg to train_curriculum_v2.py (maps to train.py's map_seed parameter).

Base objective weight analysis: 1.0/max_steps per tick. With m2_factor=5 on 3000-step episodes: 5/3000=0.00167/tick. The _apply_milestones_2 function scales this and subtracts 1 from junction count (removes home base).

## 2026-05-18 06:09 UTC: Stage 1b complete, Stage 1c starting

Stage 1b (ent=0.02, 50 epochs, 3.2M steps) completed in 23.2 min.
- Best checkpoint: `train_dir_p1_anneal_m2x5_s42/stage1b/177908317592/model_000782.pt`
- Entropy dropped from 1.609 → ~1.58 (still high, policy exploring)
- Junction.held: first half 17% nonzero avg=1321, second half 9% nonzero avg=1418
  → Policy specializing: fewer but longer alignment episodes

Stage 1c (ent=0.01, 30 epochs, 1.92M steps) now running. ETA ~13 min.

Also added temperature support to TutorialPolicy (default 0.7 for eval, matching previous sessions).

## 2026-05-18 06:24 UTC: Stage 1c complete, Phase 2 Experiment 1 starting

Stage 1c (ent=0.01, 30 epochs, 1.92M steps) completed in 14.3 min.
- Best checkpoint: `train_dir_p1_anneal_m2x5_s42/stage1c/177908456867/model_000469.pt`
- Total Phase 1 time: 17.1 + 23.2 + 14.3 = 54.6 minutes (7.04M total steps)

**Bug fix**: temperature in eval scripts needed `kw.temperature=0.7` format (not `temperature=0.7`).
Policy parser requires `kw.` prefix for kwargs passed to policy constructor.

Phase 2 Experiment 1 started: map42 + seed42 + m2x5
- 30 epochs, 5.76M steps on competition map (88x88), 3000-step episodes
- ent=0.01, clip=0.2, lr=0.00092
- Warm-starting from Phase 1 Stage 1c best checkpoint
- ETA ~38 min at ~2500 SPS

Early Phase 2 observations:
- Entropy at ~1.11 (down from 1.58 in Stage 1b)
- junction.held = 0 for all early epochs — model hasn't adapted to competition map yet
- Clips junction.held = 183120 (clips dominating)

## 2026-05-18 06:54 UTC: Phase 2 direct FAILED, starting graduated pipeline

Phase 2 direct (arena → 3000-step compmap) confirmed failure:
- Only 1/96 epochs had non-zero junction.held (748.0)
- Entropy collapsed from 1.29 → 0.66 (near-deterministic policy not doing alignment)
- Model never learned to navigate competition map from arena training alone
- Killed process at ~45% completion to free CPU

**Root cause**: Jump from 1000-step arena to 3000-step competition map is too big.
Previous sessions (Session 2) used intermediate 1000-step competition map phase.

**Fix**: Added `compmap_graduated` pipeline with two sub-phases:
- Phase 2a: 1000-step episodes on competition map, ent=0.02 (learn map navigation)
- Phase 2b: 3000-step episodes on competition map, ent=0.01 (extend horizon)

## 2026-05-18 06:55 UTC: Phase 2a (graduated) results

Phase 2a (20 epochs, 1.28M steps, 1000-step episodes, ent=0.02) completed in 9.7 min.
- 24 non-zero junction.held values (vs 1 for direct Phase 2)
- Later epochs showed increasing values: 1710, 1161, 1742 (model actively learning alignment)
- Entropy stayed healthy at ~1.56
- Best checkpoint: `train_dir_p2a_1kep_m2x5_s42_ms42/177908726890/model_000313.pt`

Phase 2b (3000-step episodes) now running from Phase 2a best. ETA ~45 min.
