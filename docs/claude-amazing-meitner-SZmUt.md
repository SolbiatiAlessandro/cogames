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

Untrained LSTM on competition map (cogsguard_machina_1.basic, 8 cogs, 1000 steps):
- Per-agent reward: ~0.10 (10 episodes)

### 2026-05-16 07:15: RL training attempt 1 — braveheart arena

Started training: cogsguard_arena.basic + no_vibes + braveheart + credit + milestones_2

**Key findings about training infrastructure:**
- `credit` and `milestones_2` are REWARD variants (not mission variants)
- CLI's `--variant` flag only handles mission variants
- Created custom training script (scripts/train_rl_fixed_map.py) that applies reward variants properly
- Training on Serial backend (CPU only) is very slow: 180-450 SPS
- 5M steps @ 200 SPS = ~7 hours — too slow for this session

**After 5 epochs of RL training (braveheart arena + credit + milestones_2):**
- aligned.junction.held: 0.0 (no progress)
- entropy: 1.609 → 1.596 (barely decreasing)
- Per-episode reward: ~-0.78 (negative due to milestones_2 adjustment)

**Root cause analysis:** Same issues as previous researchers — RL from scratch is too slow to discover navigation to distant junctions. The reward signal is too sparse.

### 2026-05-16 07:30: Behavioral cloning from scripted policy

**New approach: imitation learning.** Instead of RL from scratch:
1. Collect (observation, action) pairs from the scripted MachinaRolesPolicy
2. Train the TutorialPolicyNet (CNN+LSTM) to imitate those actions via supervised learning
3. Then fine-tune with RL

Collected 5000 timesteps x 8 agents = 40,000 training pairs from scripted policy.

**Scripted policy action distribution:**
- noop: 0%
- move_north: 3.3%
- move_south: 34.4%
- move_west: 36.6%
- move_east: 25.7%

BC training epoch 1: loss=0.6492, accuracy=72.95% — fast convergence!

**Hypothesis:** BC-pretrained policy will have basic navigation ability (navigate toward junctions), which RL fine-tuning can improve further. This bypasses the exploration bottleneck that pure RL faces.
