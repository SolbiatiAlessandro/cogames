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
