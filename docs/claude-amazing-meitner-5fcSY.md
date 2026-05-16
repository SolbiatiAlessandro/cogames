# Experiment Log: claude/amazing-meitner-5fcSY
## Issue: #75 — RL Curriculum Training Phase 2+3 on Competition Map

### 2026-05-16 10:00: Autoresearch starting

**My plan is to:** Continue RL curriculum training from issue #75. Previous session on branch `claude/amazing-meitner-SZmUt` achieved:
- Phase 1a "minimal_align" peak: 7.78/agent on simplified setup (flat map, no clips, start-aligner, boost-aligner=5.0)
- Phase 2a from Phase 1a warm-start: growing 1.10→1.81/agent at max_dist=10
- Competition map direct training: epoch 90 best at 0.072/agent (1.4 junctions, 223 held ticks)

No checkpoints survived from previous session (ephemeral container). Must retrain from scratch.

**Key learnings from previous sessions to apply:**
1. 5-action space (no_vibes) is correct — matches top policies
2. Entropy annealing (0.08→0.01 over 30% training) CRITICAL to prevent collapse
3. Arena training doesn't transfer to competition map — train on competition map directly
4. Close-junction curriculum (max_dist=6) works for initial learning
5. CPU training: ~2400 SPS with 16 envs, ~2M steps in 13 min

**Strategy:** Use `cogames tutorial train` CLI with proper variant configuration. Start Phase 1 on competition map with close junctions, then chain to Phase 2/3.

### 2026-05-16 10:00: Running baseline evaluation
