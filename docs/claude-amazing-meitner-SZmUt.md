# Experiment Log: claude/amazing-meitner-SZmUt
## Issue: #41 — RL policy training

### 2026-05-16 07:00: Autoresearch starting

**My plan is to:** Continue RL training work from previous sessions on issue #41. The previous researcher (branch claude/amazing-meitner-0j5Ye) made significant progress identifying the core challenges:

1. 5-action space (NoVibes) is the right approach — matches top RL policies
2. Training metrics are misleading due to per-env map randomization
3. Hub-departure problem: agents can't navigate 15+ tiles to junctions with 13x13 obs
4. Entropy collapse is universal across all configs
5. Credit rewards necessary for learning the mining chain but cause hub-trapping

**My hypothesis:** The navigation bottleneck can be solved by:
1. Training with a FIXED map seed (same map across all envs) so the model learns actual spatial navigation rather than averaging over random layouts
2. Adding an exploration reward (cell.visited) with higher weight to incentivize map exploration
3. Using entropy annealing to prevent premature convergence
4. Starting with the NoVibes (5-action) + credit + milestones_2 reward configuration

**Key insight from previous work:** All prior training used random map seeds per env (seed = base_seed + env_index), so alignment metrics were averaged over 256 different maps. ~36% of random maps happen to have junctions close to hub. The model never learned real navigation — it just got lucky on some maps.

### 2026-05-16 07:00: Starting baseline run
