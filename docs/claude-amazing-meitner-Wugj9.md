# Experiment Log: claude-amazing-meitner-Wugj9
## Issue #75: RL Curriculum Training — Phase 2+3 on Competition Map

## 2026-05-17 17:10 UTC: Autoresearch starting

Plan: Continue RL curriculum training from issue #75. Previous sessions achieved:
- tightclip_e80: 0.123 avg @500 steps (best short-episode)
- p2lr_e20: 1.124 avg @10K (best competition length)
- withclips_e10: 1.053 avg @10K (corrected from initial 1.371)
- All models plateau at ~1.05 avg @10K steps

Key findings from prior work:
- clip_coef=0.1 solves entropy collapse (the "tightclip" discovery)
- 1000-step episodes are the sweet spot for training
- Competition map training is essential (arena doesn't transfer)
- Phase 2 (max_dist=10) is the curriculum sweet spot
- temp=0.7 at eval time gives free 15% improvement

No checkpoints available in fresh environment — training from scratch.

My plan:
1. Start Phase 1 training from scratch with proven best config (tightclip, competition map, 1000-step episodes)
2. Attempt tournament submission with Softmax token
3. Try new ideas: mixed-distance training, larger obs window, 8-agent training

## 2026-05-17 17:15 UTC: Starting Phase 1 baseline training

Training from scratch with optimal hyperparameters:
- clip_coef=0.1, ent_annealing 0.04→0.01 over 50%
- boost_aligner=5.0, max_dist=6
- 1000-step episodes, competition map
- 8 cogs (full team), 16 envs (CPU-friendly)

## 2026-05-17 17:25 UTC: Training in progress, auth blocker identified

Training running at ~2.5K SPS. Epoch 109 reached, entropy at 1.22 (still healthy).
Checkpoints saved every 5 epochs up to epoch 70 so far.

**Auth blocker**: Softmax token works for read (leaderboard shows us at #5 with 41.85)
but fails for write operations (upload, my policies). Browser-based OAuth2 required
but can't be done from this environment. Tournament submission remains blocked.

## 2026-05-17 17:30 UTC: Evaluating early checkpoints

Running eval_rl.py on epoch 60 checkpoint at 500 steps. Eval competing with
training for CPU resources — runs slowly.

## 2026-05-17 17:35 UTC: CRITICAL FINDING — 8-agent training produces broken model

Evaluated epoch 80 (trained with 8 agents):
- @500 steps: avg=0.065, peak=0.075 (4/5 episodes dead at 0.050)
- @1000 steps: avg=0.100 (all episodes at base survival, zero junction alignment)
- cogs/aligned.junction.held = 0.0 — model NEVER aligns junctions
- aligner.gained = 1.625 (picks up gear) but heart.gained = 0.125 (never withdraws hearts)

Previous session's tightclip_e80 (trained with 4 agents): avg=0.123 @500, avg=0.375 @1000

Root cause: Training with 8 agents on competition map prevents learning the alignment pipeline.
With 8 agents, there's too much congestion at hub, reward signal is too sparse per agent.

Fix: Restarted training with 4 agents (matching previous session's successful config).

## 2026-05-17 17:38 UTC: Restarted Phase 1 training with 4 agents

Config: Same tightclip config but --cogs 4 instead of 8.
This matches the previous session's successful training pipeline.

## 2026-05-17 18:00 UTC: CRITICAL — From-scratch competition map training TOTAL FAILURE

Evaluated all 4-agent checkpoints (e40, e60, e80, e100, e105):
- ALL produce 0.050 @500 steps (pure survival)
- ALL produce 0.100 @1000 steps (pure survival)
- ZERO junction alignment across 25+ episodes
- Model learns hub interactions (heart withdrawal, aligner pickup) but never navigates to junctions

Root cause: `patch_junction_distance(max_dist=6)` doesn't control junction PLACEMENT on competition
maps. The `EnsureHubReachableJunctionConfig` only guarantees at least one junction reachable
within max_distance, but the main junction distribution (Poisson across 88×88 map) still scatters
junctions far from hub. The reward signal for junction alignment is too sparse for random
exploration to discover.

Previous sessions' success came from the arena-first pipeline:
1. Train on arena (where close junctions ARE the only junctions) — agent learns alignment
2. Warm-start on competition map — agent already knows alignment, just adapts navigation

## 2026-05-17 18:05 UTC: Started Phase 1 arena training

Pivoting to arena-first approach. Config:
- mission: cogsguard_arena.basic (NOT competition map)
- max_dist=6, clip_coef=0.1, ent 0.04→0.01, boost_aligner=5.0
- 1000-step episodes, 4 cogs, 16 envs
- 4M steps total, checkpoint every 5 epochs
- Patching confirmed working: "Patched MachinaArena.get_children max_distance to 6"

Plan: Train arena to ~e60-80, eval, then warm-start Phase 2 on competition map.

## 2026-05-17 18:20 UTC: Arena training ALSO fails — no alignment after 80 epochs

Evaluated arena-trained checkpoints (e30-e80) on both arena and competition map.
Results: ALL 0.500 (arena baseline) or 0.050 (competition baseline), ZERO junction alignment.

Detailed stats show agents explore (cell.visited up to 49K), pick up random gear (solar,
carbon, aligner, miner), but NEVER withdraw hearts and NEVER align junctions.

Root cause: training without simplifications (start-aligner, start-heart, flat-map, no-clips)
requires agents to discover a 3-step sequence through random exploration:
1. Pick up aligner gear from station
2. Withdraw heart from hub
3. Navigate to junction and align

This is too sparse for RL to discover from scratch.

## 2026-05-17 18:25 UTC: KEY DISCOVERY — Original Phase 1 used --start-aligner --start-heart

Re-read previous session's (claude/amazing-meitner-9HeB9) experiment log. Phase 1 was
"minimal_align" config: --start-aligner --start-heart --flat-map --no-clips.

This eliminates the discovery problem: agents START with gear, just need to navigate to
junctions. Much easier for random exploration to stumble upon alignment.

The full successful pipeline was:
1. Phase 1: minimal_align on arena (flat, no clips, start with gear)
2. Phase 2a: natural terrain on competition map from P1 weights
3. Phase 2b (compmap_v1): max_dist=6 on competition map
4. longep: 2000-step episodes from compmap_v1 (entropy breakthrough)
5. sprint_compmap → midep_compmap → midep_tightclip (best model)

Restarted training with correct minimal_align config. Training running.

## 2026-05-17 18:40 UTC: MODEL IS LEARNING — eval was wrong

Evaluated minimal_p1 e60 on MATCHING environment (flat arena, start-gear, max_dist=6):

| Steps | Avg reward | Peak reward | Junctions aligned |
|-------|-----------|-------------|-------------------|
| 500   | 0.940     | 1.393       | 1-2/episode       |
| 1000  | 1.649     | 1.979       | 0-1/episode       |
| 2000  | 4.549     | 7.715       | 1-3/episode       |

Previous evals showed 0.050/0.500 because they evaluated on DIFFERENT environments
(non-flat arena without start-gear, or competition map). The model IS learning alignment.

The peak of 7.72 @2000 steps matches previous session's Phase 1 peak of 7.78!

Resumed training from e60 weights for continued improvement.

Plan:
1. Let Phase 1 train to e80+ equivalent
2. Start Phase 2: warm-start on competition map (natural terrain, no clips)
3. Phase 3: full competition map with clips
4. Eval at each stage

## 2026-05-17 18:50 UTC: Phase 2 started on competition map

Resumed Phase 1 for 20 more epochs (e60→e80 equivalent). Then started Phase 2:
- Competition map (cogsguard_machina_1.basic), natural terrain
- max_dist=6, no clips, NO start-gear (full pipeline learning)
- Warm-start from Phase 1 e80 equivalent checkpoint
- clip_coef=0.1, ent 0.04→0.01, boost_aligner=5.0
- 1000-step episodes, 4 cogs, 16 envs

The model transitions from simplified (flat map, start with gear) to realistic
(natural terrain, must find gear). Expect initial U-curve degradation then recovery.

## 2026-05-17 19:05 UTC: Phase 2 transfer failures — all approaches show 0.050 flat

Both Phase 2 attempts failed:
- **compmap_from_p1** (no start-gear): 0.050 @500, 0.100 @1000 after 30 epochs
- **compmap_gear** (with start-gear): 0.050 @500, 0.100 @1000 after 30 epochs
- Agents never align junctions on competition map despite working well on flat arena

Root cause analysis:
1. Competition map is 88×88 with Poisson-distributed junctions — most are FAR from hub
2. EnsureHubReachableJunctionConfig adds only ONE close junction, but navigation is still hard
3. Agents trained on 50×50 flat arena don't know how to navigate 88×88 natural terrain

## 2026-05-17 19:15 UTC: New strategy — gradual transition experiments

Running parallel experiments to find the right transfer path:

1. **compmap_flat_v2**: Competition map + flat terrain + start-gear + high entropy (0.08→0.02/80%)
   - Tests map-size adaptation only (50×50 → 88×88), keeping flat terrain
   - Junction alignment appeared at epochs 3-5 (held=118→423) in v1 before entropy collapse
   - v2 fixes entropy with higher ent_start=0.08

2. **compmap_longep_v2**: Competition map + natural terrain + start-gear + 2000-step episodes
   - Tests whether longer episodes help discover junctions (previous session breakthrough)
   - Also fixed: added --start-aligner --start-heart (agents weren't finding aligner gear)
   - Entropy rising healthily: 1.23 → 1.40 (from v1 data)

Key insight from v1 experiments:
- compmap_flat showed junction alignment (held=423) at epoch 5 — FIRST TIME any competition
  map training showed alignment in this session!
- But entropy collapsed (1.23→1.12) due to ent_start=0.04 being too low
- Longep entropy was healthy (1.23→1.40) with ent_start=0.08 — applying same fix to both

## 2026-05-17 19:35 UTC: BREAKTHROUGH — compmap_flat_v2 shows consistent junction alignment

**compmap_flat_v2** (competition map + flat terrain + start-gear + ent 0.08→0.02/80%) is learning:

Training junction.held trajectory:
| Epoch | held values | Note |
|-------|------------|------|
| 3 | 223 | First alignment on competition map! |
| 4 | 0 | |
| 5 | 293 | Growing |
| 6 | 0 | |
| 7-8 | [0, 487] | Peak in multi-env eval |
| 8-9 | [0, 0] | |
| 9 | 0 | |
| 10 | 628 | Strong |
| 11 | [675, 1408] | NEW BEST — 1408 held! |
| 12 | 808 | Consistent |
| 13 | 0 | |
| 14 | [0, 945] | |

Entropy trajectory: 1.23 → 1.40 (healthy, continuously rising)

**compmap_longep_v2** (2000-step episodes, natural terrain + start-gear): Only showed held=1170 at
ONE epoch, then back to zero. Entropy declining (1.30→1.22). Killed in favor of flat v2.

## 2026-05-17 19:50 UTC: Evaluation results on matching environment

Paused training, ran full eval of flat_v2 e15 on MATCHING environment (competition map, flat terrain, start-gear):

| Steps | Avg reward | Peak reward | Junctions aligned | Notes |
|-------|-----------|-------------|-------------------|-------|
| 500 | 0.0654 | 0.0949 | 1 in 2/5 episodes | First non-zero at 500 on compmap! |
| 1000 | 0.1673 | 0.2934 | 2-3 in 2/5 episodes | Exceeds previous 0.112 avg! |

Standard eval (without start-gear): 0.100 flat @1000 — model can't acquire gear.

**This confirms Phase 2a (map navigation) is working.** The model successfully learns to navigate
the 88×88 competition map layout and align junctions when given gear.

Next step: Phase 2b — remove start-gear to teach gear acquisition pipeline.

### Revised curriculum pipeline:
1. Phase 1: minimal_align on arena (flat, start-gear) → e60 ✓
2. Phase 2a: competition map + flat + start-gear → e80 ✓ (avg=0.0882/0.1911 @500/1000)
3. Phase 2b: competition map + flat + start-aligner → e20 (heart withdrawal learned, held=2543)
4. Phase 2b-standard: competition map + standard (2000-step longep) → IN PROGRESS
5. Phase 3: full competition (add clips) → pending

## 2026-05-17 20:10 UTC: Phase 2b experiments — gear acquisition

### learnheart (flat + start-aligner, from flat_v2 e80)
- Agents learn heart withdrawal within 4 epochs (first junction held=156 at e4)
- Peak held=2543 at epoch 17, sustained 1000-2000 held through epochs 15-30
- BUT: after ~epoch 50, alignment disappears as entropy stabilizes
- Standard eval: 0.100 flat (agents never find aligner on standard map)
- Conclusion: Heart acquisition works, aligner acquisition is the bottleneck

### Full nogear (flat + no start-gear, from flat_v2 e80)
- Agents learn some heart withdrawal (0-2.25/ep) but very sparse aligner (0-0.25/ep)
- Zero junction alignment after 25 epochs — can't get both gear pieces consistently
- Killed in favor of more gradual approaches

### Standard longep — FAILED (39 epochs, zero alignment)
- From flat_v2 e80, directly on standard competition map (no simplifications)
- 2000-step episodes, ent 0.08→0.02/80%, boost_aligner=5.0
- Zero junction alignment after 39 epochs. Entropy collapsed to 1.31.
- Root cause: model trained on flat terrain can't navigate natural terrain to find gear/junctions

## 2026-05-17 20:40 UTC: BREAKTHROUGH — Natural terrain with gear from flat_v2

### compmap_natural_gear (natural terrain + start-gear, 2000-step, from flat_v2 e115)
**Config**: cogsguard_machina_1.basic, natural terrain, max_dist=6, start-aligner, start-heart,
clip_coef=0.1, ent 0.08→0.02/80%, boost-aligner=5.0, boost-heart=2.0, explore-weight=0.001

**Junction alignment trajectory (held per epoch):**
| Epoch | held | entropy |
|-------|------|---------|
| 1 | 0 | - |
| 2 | 0 | 1.36 |
| 3 | 254 | 1.24 |
| 4 | 190 | 1.15 |
| 5 | 519 | 1.10 |
| 6 | 1811 | 1.08 |
| 7-8 | 319-1533 | 1.07-1.10 |
| 10 | 1269 | 1.17 |
| 15 | 2605 | 1.30 |

**FIRST sustained junction alignment on NATURAL terrain competition map!**
- Entropy recovered from 1.07 to 1.40 then dropped to 0.92 before recovering again
- Training ran 38 epochs before container restart killed the process
- All checkpoints lost in restart

### Key findings from this session:
1. **Graduated terrain transfer works**: flat_v2 (flat+gear) → natural+gear transitions smoothly
2. **Entropy 0.08→0.02/80% prevents collapse** through terrain adaptation
3. **Aligner station is IN the hub** (4 cells from center) — not scattered on map
4. **The pipeline**: arena flat→compmap flat→compmap natural→remove gear
5. **Arena natural from minimal_p1 FAILS** — weak model can't adapt to terrain

## 2026-05-18 — Container restart, all checkpoints lost

Restarting full pipeline from scratch with proven recipe:
1. Phase 1: minimal_align on arena (flat, start-gear, 2000-step, clip_coef=0.1)
2. Phase 2a: competition map + flat + start-gear
3. Phase 2b: competition map + natural terrain + start-gear
4. Phase 2c: remove gear, full competition

## 2026-05-18 ~21:00 UTC: Full pipeline rebuilt from scratch

### Phase 1 v2 (flat arena, start-gear, 2000-step)
- Trained 35 epochs, junction alignment from epoch 3
- Junction held grew to 4576 by epoch 28
- Phase 1 e25 eval: avg=3.985 @2000 matching env (but junction stats show aligned_by_agent=1)

### Phase 2a: compmap_flat_v3 (flat competition map, start-gear, from P1 e35)
- Trained 50 epochs at 1200 SPS (fast on flat terrain)
- Junction held trajectory: appeared at e2 (114-332), peaked at e15 (2799)
- Two entropy collapses: 0.99→0.82 (e1-5) and 1.37→0.52 (e17-39), both recovered
- Eval e20 matching env: avg=0.133, peak=0.183 @1000 steps

### Phase 2b: compmap_natural_from_p1 (natural terrain, start-gear, from P1 e35)
**Config**: cogsguard_machina_1.basic, natural terrain, max_dist=6, start-aligner, start-heart,
clip_coef=0.1, ent 0.08→0.02/80%, boost-aligner=5.0, boost-heart=2.0, explore-weight=0.001

**Junction held trajectory:**
| Epoch | held |
|-------|------|
| 3 | 169 |
| 4 | 325 |
| 8-9 | 515, 328 |
| 10 | 1995, 827 |
| 11 | 1195 |
| latest | 1021 |

**Eval results (natural_from_p1 e20):**
| Environment | Steps | Avg | Peak | junc_aligned |
|------------|-------|-----|------|-------------|
| Matching (natural, gear) | 1000 | **0.183** | **0.226** | 4/5 episodes |
| STANDARD (no gear, 8 cogs) | 500 | **0.060** | **0.098** | 1/5 episodes! |

**BREAKTHROUGH: First non-zero junction alignment on standard competition eval!**
- Agents learn to find aligner station (3/5 episodes)
- Agents learn heart withdrawal (4/5 episodes)
- 1/5 episodes achieve full pipeline (gear + heart + navigate + align)

Training continuing from e25 for further improvement.

## 2026-05-18 ~21:30 UTC: Phase 2c FAILED — Pivoting to graduated gear removal

### Phase 2c: compmap_natural_nostart (NO gear, from natural_from_p1_cont e40)
**Config**: natural terrain, NO start-gear, max_dist=6, clip_coef=0.1,
ent 0.08→0.02/80%, boost-aligner=5.0, boost-heart=3.0, explore-weight=0.001

**Result: FAILED after 68 epochs**
- Junction alignment: ZERO across all 68 epochs
- Gear acquisition: sporadic 0-1.5/epoch (agents occasionally find gear but never use it)
- Entropy oscillates 0.77-1.26 (classic policy instability — cycling)
- Model can't learn full gear acquisition pipeline from scratch

**Root cause**: Credit assignment chain too long — agents must: find hub → find aligner station →
get resources → craft aligner → find heart station → withdraw heart → navigate to junction → align.
With only 2000 steps and sparse rewards, impossible to discover from random exploration.

### Phase 2c-alignonly: start-aligner, learn heart + navigation (PROMISING!)
**Config**: natural terrain, start-aligner (NO start-heart), max_dist=6, clip_coef=0.1,
ent 0.08→0.02/80%, boost-aligner=5.0, boost-heart=5.0, explore-weight=0.005

**Junction held trajectory:**
| Epoch | held | heart.gained | entropy |
|-------|------|-------------|---------|
| 0 | [0, 0] | [0, 2.0] | - |
| 1 | [60, 0] | [0.25, 0] | - |
| 5 | 0 | 0 | 0.94 |
| 6 | 0 | 2.0 | 0.91 |
| 10 | **592** | **1.0** | 0.89 |
| 11-15 | 0 | 0 | 0.91-0.98 |

**BREAKTHROUGH at epoch 10: junction.held=592 without start-heart!**
- First time agents align junctions by acquiring hearts from scratch
- Model learns: start with aligner → withdraw heart → navigate to junction → align
- Credit assignment chain halved vs full no-gear: only 3 steps instead of 6
- Sporadic (not every epoch) but REAL alignment events

**Competition discovery**: Tournament uses max_steps=10000 (not 2000). Longer episodes
give agents much more time for gear acquisition + junction navigation.

### Flat terrain learnheart: from flat_v3 e50, start-aligner only
**Config**: flat competition map, start-aligner (NO start-heart), max_dist=6, clip_coef=0.1,
ent 0.08→0.02/80%, boost-aligner=5.0, boost-heart=3.0, explore-weight=0.001

**Junction held trajectory (growing per cycle):**
| Epoch | held | heart.gained | Note |
|-------|------|-------------|------|
| 3 | 312 | 0.75 | First alignment (same env base) |
| 14 | 737 | - | After first entropy cycle recovery |
| 27 | 1068 | - | Second peak |
| 32 | **1957** | - | **BEST** — growing with each cycle |

**Entropy cycles**: 1.10→0.82→1.38→0.70→recovering
Each entropy cycle produces a junction alignment event, with magnitude growing.

**Learnheart e20 (old session) eval results — key comparison:**
| Environment | Steps | Avg | Peak | junc_aligned |
|------------|-------|-----|------|-------------|
| Standard (no gear) | 1000 | 0.100 | 0.100 | 0/5 ep |
| start-aligner | 1000 | **0.119** | **0.152** | 2/5 ep |
| start-aligner | 2000 | **0.236** | **0.381** | 2/5 ep |

**Key insight**: learnheart e20 with start-aligner at 2000 steps exceeds Phase 2b!
The graduated approach (start-aligner only, learn heart acquisition) works better
than Phase 2b (start with both, try to learn full pipeline).

### Learncraft v1: NO gear + resource rewards (FAILED)
**Config**: flat terrain, NO starting gear, resource collection rewards (weight=2.0)
for germanium/carbon/oxygen/silicon. Base: flat_v3 e50 (never saw alignment behavior).
**Result**: Entropy collapsed (0.84 at epoch 10). Killed at epoch 10. The base model
didn't know alignment behavior, so removing gear left it with no useful policy.

### Flat learnheart training (KILLED)
**Config**: flat terrain, start-aligner, from flat_v3 e50. 65 epochs.
**Result**: Junction.held up to 82080 (max), but junction alignment events sporadic
(9/290 readings non-zero). On natural terrain eval: avg=0.100, zero junctions.
**Conclusion**: Flat→natural terrain transfer is poor. Natural terrain training is better.

### Learncraft v2: Graduated from learnheart — ALIGNER CRAFTING BREAKTHROUGH
**Config**: natural terrain, NO starting gear, resource rewards=5.0, from learnheart e20 base.
Higher entropy start (0.10→0.02 over 80%). boost-aligner=5.0, boost-heart=3.0.
**Key difference from v1**: Base model knows alignment behavior (learnheart), so removing
gear is a smaller step. Higher ent_start prevents collapse.

**Resource collection progress (by epoch):**
| Resource | Needed for Craft | e5 | e10 | e25 | e42 | Trend |
|----------|-----------------|-----|------|------|------|-------|
| Oxygen | 1 | 3-4 | 4-12 | 3-4 | 2-12 | Consistent ✅ |
| Germanium | 1 | 0 | 0.25 | 0.5-1.5 | 0-0.75 | Sporadic ↗ |
| Carbon | 3 | 0 | 0.25 | 0.5-1.0 | 0-0.5 | Bottleneck ⚠️ |
| Silicon | 1 | 0 | 1.0 | 0-0.75 | 0-0.75 | Sporadic |
| Heart | (for alignment) | 0.25 | 0.25 | 0-0.5 | 0-1.25 | From base model |

**Milestones:**
- e7-8: **First aligner crafting event** (aligner.gained=0.25) — agent collected resources and crafted!
- e10: Standard eval shows aligner=1, heart=1 in 1/5 episodes
- e42: Entropy cycling (trough 0.925, recovered to 1.06) — healthy
- e59: Training ongoing

**Standard eval (learncraft_v2 e10, no gear, 8 cogs):**
| Episode | avg_reward | aligner.gained | heart.gained | junc_aligned |
|---------|-----------|----------------|-------------|-------------|
| 0 | 0.100 | 0 | 0 | 0 |
| 1 | 0.100 | **1** | **1** | 0 |
| 2 | 0.100 | 0 | 0 | 0 |
| 3 | 0.100 | 0 | 0 | 0 |
| 4 | 0.100 | 0 | 0 | 0 |

**Insight**: First model to craft an aligner from scratch in standard eval!
No junction alignment yet at 1K steps — need longer eval or more training.
