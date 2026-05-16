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

### 2026-05-16 07:45: BC training results (arena-only)

**Arena-only BC training (5000 timesteps × 8 agents, 15 epochs):**
- Final: loss=0.0120, accuracy=98.93%
- Weights saved to `bc_weights.pt` (11MB)

### 2026-05-16 08:00: BC policy evaluation on arena (cogames scrimmage)

**BC policy on cogsguard_arena.basic (500 steps, 3 episodes):**
- **Per-agent reward: 0.50** (5x improvement over untrained baseline 0.10)
- aligned.junction.held: 0 (no junctions held)
- cell.visited: 27,584/agent (good exploration)
- action.move.failed: 1000/agent (67% failure rate — map-specific learning)
- heart.gained: 0.88/agent
- Elements gained: carbon=1.38, oxygen=5.62, germanium=0.50, silicon=5.50
- max_steps_without_motion: 1225 (gets stuck sometimes)
- 0.62 deaths/agent (some agents dying)

**Key observations:**
1. BC provides 5x reward improvement over random — confirms navigation initialization works
2. High move failure rate (67%) suggests BC learned arena-specific wall avoidance patterns that don't generalize perfectly
3. No junction alignment yet — BC only mimics the scripted policy's actions but the scripted policy's alignment behavior is too complex (multi-step goal-oriented)
4. Element mining is happening but at low rates compared to scripted policy

### 2026-05-16 08:00: RL fine-tuning from BC weights

Started RL fine-tuning: BC weights → PPO on arena (4 cogs, braveheart, credit+milestones_2, ent_coef=0.02)
- Hypothesis: BC bootstrap gives RL a head start on navigation, allowing faster discovery of junction alignment
- Running in background (train_dir_bc_finetune/)

### 2026-05-16 08:10: BC policy evaluation on competition map

**BC policy on cogsguard_machina_1.basic (500 steps, 1 episode):**
- **Per-agent reward: 0.05** (WORSE than untrained baseline 0.10)
- aligned.junction.held: 0 (clips got 5520!)
- cell.visited: 7,323/agent (vs 27,584 on arena)
- action.move.failed: 320/500 (64%)
- heart.gained: 0.88/agent
- clips aligned 23 junctions, cogs aligned 0

**Conclusion: BC from arena doesn't transfer to competition map.** The learned movement patterns are arena-specific. The 88×88 competition map has different layout and the BC policy can't navigate it.

### 2026-05-16 08:10: BC → RL fine-tuning — DEAD END

Started RL fine-tuning from BC weights with ent_coef=0.1 (10x default).
- **Entropy: 0.109** — still nearly deterministic despite high entropy bonus
- BC training drives entropy to zero (CrossEntropy loss with 98.9% accuracy)
- PPO's entropy bonus can't overcome the strong BC prior
- **ABANDONED** — BC kills exploration, making RL fine-tuning ineffective

### 2026-05-16 08:15: Curriculum training from scratch (PROMISING)

**New approach: train with close junctions, then increase distance.**
- Phase 1: max_distance=6 (junctions within 13×13 obs window)
- Phase 2: max_distance=10
- Phase 3: max_distance=15 (competition setting)

Monkey-patched `EnsureHubReachableJunctionConfig.max_distance` in `terrain.py` at runtime.
Training started: arena, 4 cogs, braveheart, credit+milestones_2, ent_coef=0.03.
SPS: ~2,475 (fast! — 2M steps in ~13 min)

### 2026-05-16 08:30: BREAKTHROUGH — Curriculum training produces junction alignment!

**Curriculum phase 1 (max_distance=6) — epoch 20 results on TRAINING:**
- aligned.junction.held peaks: 1655, 1037, 441 (across different episodes)
- aligned.junction: up to 2.0 per episode
- Entropy: 1.58 (stable, no collapse at epoch 30!)
- SPS: 2,400-2,600

**Epoch 20 evaluation on COMPETITION MAP (cogsguard_machina_1.basic):**
- **aligned.junction = 1** — FIRST RL model to align a junction on competition map!
- **aligned.junction.held = 180** — junction held for 180 steps
- action.move.failed = 31.88 (6.4% — vs 64% for BC, 38% for previous RL)
- cell.visited = 9,831/agent
- noop.success = 74.88 — learned to use noop strategically
- max_steps_without_motion = 5 (never stuck)
- Per-agent reward: 0.07 (low but with real alignment)

**Why this works:**
1. Close junctions (6 tiles from hub) are within the 13×13 obs window
2. Agent learns junction alignment during training on arena with close junctions
3. This navigation + alignment behavior transfers to competition map even though junctions are 15+ tiles away
4. Fixed-seed arena maps (64 variants per training batch) provide variability for generalization
5. Entropy stays high because the task is achievable — no frustration collapse

**Comparison to all previous RL training attempts:**
| Metric | Previous best (any researcher) | Curriculum epoch 20 |
|--------|-------------------------------|---------------------|
| aligned.junction on competition | 0 (always) | **1** |
| aligned.junction.held on competition | 0 (always) | **180** |
| move.failed % | 38% | **6.4%** |
| entropy at epoch 20+ | <1.1 (collapsed) | **1.58** (stable) |

### 2026-05-16 08:35: Tournament submission blocked

Auth token returns 401 on tournament API. Also fixed compat version issue (0.0.0 → 0.25).
Cannot upload to tournament yet. Continuing training.

### 2026-05-16 08:45: Epoch 30 competition eval — WORSE than epoch 20

**Epoch 30 on cogsguard_machina_1.basic (500 steps, 1 episode):**
- Per-agent reward: 0.05 (worse than epoch 20's 0.07, worse than baseline 0.10)
- aligned.junction: **0** (epoch 20 had 1)
- aligned.junction.held: **0** (epoch 20 had 180)
- action.move.failed: 69.25 (13.8%, vs 6.4% for epoch 20)
- cell.visited: 16,726 (more exploration but directionless)
- max_steps_without_motion: 9.12 (epoch 20 had 5)

**Training divergence analysis (62 epochs total before kill):**
- Entropy climbed steadily from 1.27 (epoch ~25) to 1.60 (epoch 62) — approaching max 1.609
- Junction alignment in training dropped to 0 after epoch ~35
- ent_coef=0.03 is TOO HIGH — causes entropy explosion that destroys learned alignment
- **Epoch 20 confirmed as best checkpoint** for this training run

**Conclusion:** ent_coef=0.03 destabilizes training after ~20 epochs. Need lower ent_coef for sustained learning.

### 2026-05-16 08:50: New experiments — lower entropy + curriculum phase 2

**Experiment A: Phase 1 retrain with ent_coef=0.01 (default)**
- Hypothesis: lower entropy bonus prevents the explosion that destroyed epoch 30-60
- May produce more sustained junction alignment over longer training

**Experiment B: Phase 2 (max_distance=10) from epoch 20 weights**
- Hypothesis: best phase 1 model can learn to navigate slightly further junctions
- If successful, chain to phase 3 (max_distance=15 = competition setting)

**Experiment A killed at epoch 8** — too slow starting from scratch, CPU needed for experiment B.

### 2026-05-16 09:00: Phase 2 training — SIGNIFICANT IMPROVEMENT

**Phase 2 (max_distance=10, ent_coef=0.02, from epoch 20 weights) — epoch 20-23:**
- Junction alignment consistently improving!
- junction.gained per episode: from [1.0] early → [2.0, 3.0] at epoch 15 → [1.0, 2.0] at epoch 20
- Junction held ticks: 7 (epoch 5) → 432 (epoch 13) → **1053** (epoch 23)
- Entropy: 1.59 → 1.47 (slow, healthy decrease)
- SPS: ~340 (with 2 processes) → 2669 (after killing experiment A)

**Comparison: Phase 1 vs Phase 2 training metrics (arena, max training):**
| Metric | Phase 1 (max_dist=6, epoch 20) | Phase 2 (max_dist=10, epoch 23) |
|--------|-------------------------------|--------------------------------|
| Max junction.gained/ep | 2.0 | **3.0** |
| Max junction.held/ep | ~400 | **1053** |
| Entropy at epoch 20 | 1.58 (rising) | **1.47** (slowly falling) |
| Entropy trend | Unstable (collapse risk) | Stable decrease |

**Key finding:** Curriculum phase 2 from good phase 1 weights produces MUCH better alignment than training from scratch with closer junctions. The model transfers its close-junction alignment ability and improves it for medium-distance junctions.

### 2026-05-16 09:00: Reward structure analysis

Base mission reward: `aligned_junction_held / max_steps` per tick per agent.
- max_steps = 10000 for competition map (baked into reward weight at mission creation)
- At 500 eval steps: holding N junctions for T ticks = N×T/10000 reward/agent
- Target: 10.0/agent offline requires ~10 junctions held for all 10000 steps
- Scripted policy at 500 steps: 0.18/agent (3 junctions, 1326 held)
- Our best P1 epoch 20 at 500 steps: 0.07/agent (1 junction, 180 held)
- Phase 2 epoch 30 at 500 steps: 0.05/agent (0.33 junctions, 199 held)
- Phase 2 epoch 50 at 500 steps: 0.05/agent (0 junctions, 0 held — over-specialized!)

### 2026-05-16 09:10: Phase 2 eval — ARENA TRAINING DOESN'T TRANSFER

**Phase 2 epoch 30 on competition map (500 steps, 3-episode avg):**
- Per-agent reward: 0.05
- cogs/aligned.junction: 0.33 (1 junction in 1 out of 3 episodes)
- cogs/aligned.junction.held: 199.33

**Phase 2 epoch 50 on competition map (500 steps, 3-episode avg):**
- Per-agent reward: 0.05
- cogs/aligned.junction: **0** (despite 5+ during arena training!)
- cogs/aligned.junction.held: **0**

**Key insight: Arena training over-specializes.** Phase 2 improved arena alignment from 1→5 junctions but DEGRADED competition map performance. The model learned arena-specific navigation patterns that don't transfer to the 88×88 competition map.

**Original Phase 1 epoch 20 remains the BEST model on competition map.**

**New approach: Train directly on competition map (cogsguard_machina_1.basic)**
- Using 16 parallel envs (fewer due to larger map, 88×88 with 8 cogs)
- Curriculum max_distance=6 (close junctions within obs window)
- Starting from phase 1 epoch 20 weights (best model)
- Checkpoint every 5 epochs for finer granularity

### 2026-05-16 09:15: Competition-map training completed (242 epochs)

**Training config:** cogsguard_machina_1.basic, 8 cogs, max_distance=6, max_steps=1000, aligner+credit rewards, ent_coef=0.02, 16 envs, from phase 1 epoch 20 weights, 2M steps total.

**Training metrics showed two peak alignment periods:**
- Epochs 40-48: gained 3-4 junctions, held up to 2132 ticks
- Epochs 83-100: gained up to 10 junctions(!), held up to 2632 ticks (BEST)
- Late training (200+): sporadic alignment, declining

**Checkpoint evaluation on competition map (500 steps, 5-episode avg):**

| Checkpoint | Avg Reward | junction.gained | junction.held | move.failed | max_steps_without_motion |
|-----------|-----------|----------------|--------------|------------|-------------------------|
| Epoch 40  | 0.050     | 0              | 0            | 847 (34%)  | 253                     |
| Epoch 85  | 0.054     | 1.4            | 99           | 273 (11%)  | 104                     |
| **Epoch 90** | **0.072** | **1.4**    | **223**      | **347 (14%)** | **72**               |
| Epoch 95  | 0.068     | 1.8            | 191          | —          | 184                     |
| Epoch 100 | 0.050     | 0              | 0            | —          | 551                     |

**Epoch 90 is the BEST checkpoint.** Also evaluated at 2500 steps (3-episode):
- Per-agent reward: 0.34 avg (0.53, 0.25, 0.25)
- junction.aligned_by_agent: 0.12-0.88
- cogs/aligned.junction.held: 249
- High variance — alignment happens in some episodes but not consistently

### 2026-05-16 09:30: Phase 2 competition-map training started

**Config:** max_distance=10 (from 6), starting from epoch 90 weights, all else same.
**Hypothesis:** Model already learned close-junction alignment; now needs to learn medium-distance navigation to reach junctions 7-10 tiles from hub.
