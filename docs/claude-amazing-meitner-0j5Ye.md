# Experiment Log: claude-amazing-meitner-0j5Ye (Issue #41 — RL Policy Training)

## 2026-05-15T17:10: autoresearch starting, my plan is to...

Working on Issue #41: RL policy training. This is the highest priority issue — the scripted policy has hit a confirmed ceiling at ~42 online score, and all top policies are RL-trained.

Previous researchers incorrectly assumed this was blocked on GPU. The repo owner confirmed: "we don't need GPU, the model is small enough."

**Plan:**
1. Run the built-in LSTM training on CPU with small step counts to validate the pipeline works
2. Train for progressively larger step counts (10k, 100k, 1M)
3. Evaluate trained checkpoints offline against our scripted baseline
4. If results look promising, submit to the online tournament
5. Iterate on training hyperparameters and architecture

## 2026-05-15T17:10: starting to run baseline (scripted policy)

Running the current scripted policy to establish a baseline reward score.

## 2026-05-15T17:10: baseline result

Scripted baseline (machina_roles, 2 aligners, seed 42): **0.557 mission reward at 3000 steps**
- aligned.junction.held: 2573
- junction.aligned_by_agent: 0.375 per agent avg
- action.move.failed: 2159 (72% failure rate — agents blocking each other)

## 2026-05-15T17:11: Environment and model details

**Observation space**: (200, 3) — 200 tokens × 3 features (packed_xy, feature_id, value), uint8
- Tokens encode a 13×13 spatial view around each agent
- packed_xy: y = byte>>4, x = byte&0xF

**Action space**: 5 discrete — noop, move_north, move_south, move_west, move_east

**Default LSTM model**: Linear(600→128) → GELU → LSTM(128→128) → 5 actions = 226K params
**CNN+LSTM model**: CNN(spatial grid) + self-encoder → LSTM(256) → 5 actions = 708K params

## 2026-05-15T17:12: LSTM training started (sparse reward)

Default LSTM training on cogsguard_machina_1.basic, 30M steps, CPU.
Reward: only `aligned_junction_held` at 0.0001/tick — VERY sparse.
After 18 epochs: entropy decreased 1.6→1.35, some junction alignment appearing but minimal.
**Killed at epoch ~15 — switched to better approach.**

## 2026-05-15T17:25: starting CNN+LSTM training with reward shaping

New approach based on tutorials/TRAIN_ALIGNER.py:
- **Architecture**: CNN (spatial obs) + self-encoder + LSTM — properly handles spatial token structure
- **Reward shaping**: AlignerRewardsVariant — rewards for heart collection, aligner gear, junction alignment
- **Mission**: Arena (50×50, faster) with EASY difficulty (no clips), 8 agents, 3000 max steps
- **Training**: 10M steps, checkpoint every 25 epochs

**Hypothesis**: CNN with spatial obs processing + dense reward shaping will learn much faster than flat LSTM with sparse reward. Top policies all use spatial processing.

Training running at PID 17219.

## 2026-05-15T17:25: CNN+LSTM custom training — failed (batch too small)

Custom train_rl.py (NUM_ENVS=4, batch_size=4096) killed at epoch 38: reward 0.0000, approx_kl=0.0. Batch size was 8x too small for meaningful gradients.

Fixed to NUM_ENVS=64 (batch_size=32768), restarted. After 15 epochs (490K steps): reward still 0.0000 but approx_kl=0.001-0.006 (policy updating). Agent max_steps growing from 2→28 (agents surviving longer).

Killed custom training — switched to built-in `cogames train` CLI which:
- Uses 256 parallel envs (vs 64)
- Tutorial policy with 2.8M params (vs 708K custom)
- Proper vectorization and training infrastructure

## 2026-05-15T17:31: CLI training started (tutorial policy, aligner_tutorial mission)

```
cogames train -m aligner_tutorial -p tutorial --steps 10000000 --log-outputs --checkpoints ./train_dir_cli
```

- Architecture: TutorialPolicyNet (CNN+LSTM, hidden=512, 2.8M params)
- Mission: aligner_tutorial (4 agents, 1000 steps, Arena 50×50, EASY, AlignerRewardsVariant)
- Training speed: ~1700 SPS
- Batch size: ~65K (256 envs × 4 agents × BPTT=64)
- Estimated: first checkpoint at epoch 50 (~32 min), full 10M in ~98 min

**Competition context** (from issue #41):
- Best scripted: #5, 41.85 online (evyIm-73a-stuck15:v1)
- Best RL: #1, 45.29 online (Softy:v103)
- Gap: 3.44 points — purely architectural (RL vs scripted)
- All top-10 are RL-trained, using only move actions
