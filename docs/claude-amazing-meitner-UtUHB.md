# Experiment Log: claude/amazing-meitner-UtUHB

## Issue: #75 — RL Curriculum Training Phase 2+3 on Competition Map
## Also addressing: #76 — Submit best RL checkpoint to beta-cvc (BLOCKED by auth)

## 2026-05-19 05:15 UTC: Autoresearch starting

**Context:**
- Issue #76 (submit RL checkpoint) is the top priority but BLOCKED by expired Softmax auth token
- All API endpoints return 401 with the provided token `6PnHPiX9SWLBZhkMyHr4JJWKuUWZY29t_2CTrVDlCHs`
- Issue #75 (RL training) is the next highest priority and can proceed offline
- No checkpoints available (`.pt` files are gitignored) — must train from scratch

**My plan:**
1. Train RL from scratch using the proven best approach from branch 9HeB9
2. Use longep3k config: 3000-step episodes, entropy annealing 0.08→0.01/30%, boost-aligner=5.0, natural terrain, max_dist=6
3. Evaluate best checkpoints at 500, 1000, 2000, and 10000 steps
4. Prepare submission bundle so when auth is fixed, upload is one command
5. Target: avg reward > 1.0 at 10K steps (previous best: 1.394)

**Previous best results (from 9HeB9 branch, 8 sessions):**
- longep3k_e20: avg=1.394, peak=1.713 at 10K steps
- temp=0.7 optimal for eval
- Entropy annealing + 3000-step episodes = no entropy collapse
- Phase 3 (max_dist=15) didn't beat Phase 2 (max_dist=10)

## 2026-05-19 05:16 UTC: Starting baseline evaluation

Running scripted baseline (MachinaRolesPolicy) at 500 steps for reference.
