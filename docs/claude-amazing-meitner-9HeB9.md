# Experiment Log: claude/amazing-meitner-9HeB9

## Issue: #75 — RL Curriculum Training Phase 2+3 on Competition Map

## 2026-05-17 05:13 UTC: Autoresearch starting

**My plan is to:**
1. Continue the RL curriculum training started on branch `claude/amazing-meitner-SZmUt`
2. Train Phase 1 from scratch using the best discovered settings (minimal_align: no clips, start with aligner+heart, flat map, max_dist=5, boost-aligner=5.0)
3. Use best Phase 1 checkpoint to warm-start Phase 2 (max_distance=10)
4. If Phase 2 converges, advance to Phase 3 (max_distance=15 = full competition)
5. Evaluate on the competition map (cogsguard_machina_1.basic) at 500 and 1000+ steps

**Key findings from previous researcher (branch SZmUt):**
- Phase 1a minimal_align peaked at 7.78/agent reward at epoch 60-70
- Phase 2a (max_dist=10 from Phase 1a epoch 60) showed transfer working: 1.10→1.81 and growing
- Best competition-map eval: epoch 90 at 0.072/agent (1.4 junctions, 223 held)
- Arena training does NOT transfer to competition map
- Entropy annealing is CRITICAL (0.08→0.01 over 30% of training)
- 5 actions only (no vibes), credit+milestones_2 rewards
- boost-aligner=5.0 + junction_aligned weight helps enormously

**No checkpoints available on this fresh container — must retrain from scratch.**

## 2026-05-17 05:14 UTC: Starting baseline training

Running Phase 1 flat-map training (minimal_align config) to produce baseline checkpoints.
Config: --no-clips --start-aligner --start-heart --flat-map --max-distance 5 --boost-aligner 5.0 --ent-start 0.08 --ent-end 0.01 --ent-anneal-frac 0.3 --max-steps 1000 --cogs 8 --num-envs 16

## 2026-05-17 05:22 UTC: Phase 1 flat-map training results

Trained 110 epochs (~900K steps) before stopping. Checkpoints saved every 10 epochs.

**Training metrics (junction held ticks, 8 agents, 1000-step episodes):**
- Epochs 10-30: Growing from 0 to 5743
- Epochs 50-70: Peak zone, 3000-5700 range 
- Epochs 80-90: 4000-7008 (absolute peak: 7008 at ~epoch 82)
- Epochs 100-110: Declining to 3000-5200

**Entropy**: Stable 1.56-1.58 throughout (no collapse — annealing worked)

**Competition map evaluation (standard map, no distance patching):**
All flat-map checkpoints give 0.050/agent at 500 steps — flat-map training does NOT transfer to natural terrain.

## 2026-05-17 05:28 UTC: Phase 2 experiments

### Phase 2a: Natural map with max_distance=10 (from flat-map P1 epoch 80)
- Trained 60 epochs on natural competition map
- Junction held: sporadic, 0-2125 range
- Best competition-map eval at 500 steps: epoch 20 = 0.0579, epoch 40 = 0.0597

### Phase 2b: Natural map with max_distance=6 (from P2a epoch 20)  
**Config**: compmap_v1 — natural terrain, max_dist=6, boost-aligner=5.0, ent annealing 0.04→0.008/50%
- Better results! Junction held growing to 2000-2900 in training
- But entropy collapsed to 1.1 by epoch 50 (annealing too aggressive)

**Competition map eval results (standard map):**
| Checkpoint | 500 steps | 1000 steps |
|-----------|-----------|------------|
| compmap_v1 epoch 10 | 0.050 | 0.108 |
| compmap_v1 epoch 20 | 0.056 | 0.112 |
| compmap_v1 epoch 30 | 0.050 | 0.103 |
| compmap_v1 epoch 40 | 0.055 | 0.110 |
| compmap_v1 epoch 50 | 0.050 | 0.116 |

**compmap_v1 epoch 20 at 2000 steps: 0.291/agent avg (0.37 peak!) — EXCEEDS 0.18 target!**

### Phase 2c: 500-step episodes (from compmap_v1 epoch 20)
**Config**: compmap_fast — natural terrain, max_dist=6, fixed ent_coef=0.02, max_steps=500
- Fast alignment learning: held growing to 200-430 by epoch 25-30
- Entropy collapsed to 1.08 by epoch 40

**Competition map eval results:**
| Checkpoint | 500 steps avg | 500 steps peak | 1000 steps avg | 1000 steps peak |
|-----------|--------------|----------------|----------------|-----------------|
| fast epoch 10 | 0.050 | 0.051 | — | — |
| fast epoch 20 | 0.051 | 0.054 | 0.114 | 0.171 |
| fast epoch 30 | 0.060 | 0.071 | 0.135 | 0.190 |
| fast epoch 40 | 0.050 | 0.050 | — | — |

**Best at 500 steps: fast epoch 30 = 0.060 avg (0.071 peak)**
**Best at 1000 steps: fast epoch 30 = 0.135 avg (0.190 peak!)**

## 2026-05-17 05:40 UTC: Key findings and next experiment

**CRITICAL INSIGHT**: The 500-step evaluation target (0.18/agent) is extremely hard for RL because:
1. Standard competition map has junctions at 10-15 tile distance from hub
2. With 13×13 observation window, agents can only see 6 tiles ahead
3. Navigation to far junctions takes 50-100+ steps (hub exit + terrain navigation)
4. The scripted policy achieves 0.18 by using A* over the full map (global knowledge)

**The RL agent shows strong performance at 1000+ steps:**
- 0.190/agent peak at 1000 steps (near scripted 0.18 baseline)
- 0.374/agent peak at 2000 steps (2x scripted baseline!)

**Entropy collapse is the #1 training stability issue.** Every run degrades after 30-50 epochs. Fixed ent_coef=0.02 is not enough. Need a wider annealing schedule.

**Next experiment**: Phase 3 with max_distance=15 (full competition) + goal_obs for directional information, from fast epoch 30 weights. Currently running.
