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
