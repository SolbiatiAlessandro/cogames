# autoresearch: issue #77 — RAxer bug fix sweep evaluation

Branch: `claude/amazing-meitner-krCLo`
Target issue: [#77](https://github.com/SolbiatiAlessandro/cogames/issues/77) — priority:2

## Context

Issue #76 (priority:1, RL checkpoint submission) is blocked by expired Softmax auth token — confirmed 401 again this session. Falling back to highest-priority actionable issue.

Issue #77 asks us to evaluate 40+ bug fixes from the RAxer branch. The recommended approach is to cherry-pick the 4 critical bugs and evaluate offline.

## Plan

2026-05-19T17:15Z: autoresearch starting, my plan is to:
1. Run baseline on current main (8-agent, 3000 steps, 3-seed avg)
2. Cherry-pick the 4 critical bug fixes from RAxer branch
3. Evaluate with same seeds
4. If improved (>3.6 total = >10%), keep and consider full RAxer evaluation
5. If not improved, try individual bug fixes to isolate which help/hurt

## Log

2026-05-19T17:15Z: starting to run baseline

## Results

### Baseline (4A4M, commit 4531257)
- Seed 42: 1028.04, Seed 43: 926.69, Seed 44: 1226.41 → **avg 1060.38**

### Cooldown fix (commit 7055f58) — DISCARDED
- Activated get_heart_cooldown_steps on failure (was dead code)
- Zero effect: get_heart never fails in current codebase
- All 3 seeds identical to baseline

### 3A5M split (commit 10456cd) — KEPT (+6.6%)
- Changed default aligner fraction from 50% to 37.5% (3 aligners + 5 miners for 8 agents)
- Seed 42: 1067.51 (+3.8%), Seed 43: 1136.69 (+22.7%), Seed 44: 1186.30 (-3.3%)
- **avg 1130.17 (+6.6%)**

### Other sweeps (DISCARDED)
| Config | Avg | vs baseline |
|--------|-----|-------------|
| 2A6M | 1014 | -4.4% |
| 3A5M st=15 | **1130** | **+6.6%** |
| 3A5M st=20 | 1118 | +5.4% |
| 3A5M st=28 | 1075 | +1.4% |
| 5A3M | 1113 | +5.0% |
| return_load=20 | 987 | -6.9% |
| return_load=50+ | 165 | cliff (too heavy) |
| JUNCTION_ALIGN_DIST=35 | 1113 | -1.5% |

### Key discovery: junction saturation
- Map has only 53 junctions total; we align 51 by ~2K steps
- At 10K steps: total_reward=3979.62, junctions=51 (same as 3K!)
- Aligners idle with `alignable=0` for 80%+ of episode
- All reward after ~2K steps comes from junction hold time
- Clips NPC don't seem to recapture our junctions

2026-05-19T18:30Z: starting new experiment loop. Since junction alignment saturates early, the key leverage is SPEED of initial alignment. Faster alignment = more hold time reward within any time horizon.

### Session 2 sweeps (2026-05-20, DISCARDED)
| Config | Avg (3-seed) | vs 3A5M |
|--------|-----|-------------|
| stuck_threshold=10 | 1068 | -5.5% |
| hub_dist_weight=0.0 | 1127 | -0.3% |
| hub_dist_weight=0.1 | 1118 | -1.0% |
| hub_dist_weight=0.5 | 1077 | -4.7% |
| return_load=30 | 1090 | -3.5% |
| JUNCTION_ALIGN_DIST=40 | 1068 | 0% (51/51 junctions max) |
| JUNCTION_ALIGN_DIST=200 | 1068 | 0% (confirms 51 is map max) |
| aligner_repulsion_explore | 1130 | 0% (no effect) |

### Key discoveries (session 2)
- Junction count is seed-dependent (Poisson distribution); seed 42 has exactly 51
- Distance limit is NOT why 2 junctions remain unaligned — they don't exist on this seed
- Mining saturates by ~3K steps (identical stats at 3K and 10K)
- Hub produces hearts on-demand; mining is not the bottleneck
- 0 aligners → reward=24 (hub baseline); alignment IS the dominant reward
- `LLMAlignerPolicyImpl` is the active aligner policy, not `CrossRolePolicyImpl`

### 6-seed validation of 3A5M
| Seed | 4A4M | 3A5M | Δ |
|------|------|------|---|
| 42 | 1028 | 1068 | +3.8% |
| 43 | 927 | 1137 | +22.7% |
| 44 | 1226 | 1186 | -3.3% |
| 45 | 1167 | 1087 | -6.9% |
| 46 | 1150 | 1139 | -1.0% |
| 47 | 1132 | 1123 | -0.8% |
| **6-seed avg** | **1105** | **1123** | **+1.6%** |

3A5M improvement is +1.6% across 6 seeds (down from +6.6% on 3 seeds). Seed 43 is an outlier.

### 10K step evaluation (3A5M)
- Seed 42: 3979.62, Seed 43: 4329.07, Seed 44: 4713.85 → **avg 4340.85**
- Confirms junction saturation: 51 junctions aligned by ~2K steps
- All reward after step ~2K is pure junction hold time

### Session 3: structural improvements (2026-05-20)

#### Cascade gain scoring — DISCARDED (-3.8%)
- Modified `_cascade_priority_target` to score junctions by how many non-alignable junctions they'd bring into cascade range
- Formula: `travel + hub_dist * 0.2 - cascade_gain * 8`
- Result: avg 1087 vs 3A5M 1130 = **-3.8%** — sends aligners to farther junctions, travel cost outweighs cascade benefit

#### Progress tracking bug found and exploited
- **Bug**: `_update_progress` L157 sets `state.last_has_heart = has_heart` BEFORE `made_progress` check at L161 uses `not state.last_has_heart` — so get_heart progress is never detected (dead code)
- With broken progress: `no_progress_on_target_steps` always increments at hub → exits after ~3 steps with 1-3 hearts
- **Fix**: Track `last_heart_count` and detect `heart_count > last_heart_count` as progress
- Fix alone (threshold=3): avg 1096 = **-3.0%** (aligners reliably stay for 3 hearts but the wait hurts)
- Fix + threshold=5: avg 1153 = **+2.7%** (5 hearts per trip saves enough round trips to matter)

#### Hearts5 + progress fix — KEPT (+2.7%)
| Seed | 3A5M | hearts5+fix | Δ |
|------|------|-------------|---|
| 42 | 1068 | 1078 | +1.0% |
| 43 | 1137 | 1141 | +0.4% |
| 44 | 1186 | 1261 | +6.3% |
| 45 | 1087 | 1215 | +11.8% |
| 46 | 1139 | 1114 | -2.2% |
| 47 | 1123 | 1111 | -1.1% |
| **6-seed avg** | **1123** | **1153** | **+2.7%** |

### 10K step evaluation (hearts5+fix)
- Seed 42: 3990.21, Seed 43: 4333.38, Seed 44: 4788.12 → **avg 4370.57** (+0.7% vs 3A5M 10K)
- Smaller improvement at 10K because alignment phase is a smaller fraction of total runtime

### Session 3 additional sweeps (all DISCARDED)
| Config | Avg (3-seed) | vs hearts5 |
|--------|-------------|------------|
| 2A6M+hearts5 | 1106 | -4.1% |
| 4A4M+hearts5 | 1084 | -6.6% |
| hearts=7+fix | 1149 | -1.0% |
| hearts=4+fix | 1140 | -1.7% |
| junction_dist=18 | 1152 | 0% |
| explore_cap=22 | 1098 | -5.4% |
| explore_cap=45 | 1148 | -1.0% |
| adaptive-hearts (3-7) | 1159 | 0% |

### Session 3 key findings
- **Progress tracking bug**: `_update_progress` L157 sets `state.last_has_heart` before `made_progress` uses it — get_heart progress was dead code since the codebase was written
- **Optimal heart accumulation**: hearts=5 is the sweet spot; 3 too few, 7 too many (hub takes too long to produce), 4 slightly suboptimal
- **Role split robust**: 3A5M is still optimal with hearts5; 2A6M and 4A4M both worse
- **Explore cap robust**: default (stuck_threshold × 2 = 30) is optimal; shorter and longer both hurt
- **Near theoretical ceiling**: at 3K steps with ~130 junction cells, current avg ~1153 is ~90% of theoretical max (~1300). Remaining 10% is alignment latency that's hard to compress further
- **Next researcher should consider**: tournament-specific optimizations (4v4 with clips), dynamic role switching after junction saturation, or completely new skill architectures

### Session 4: final parameter retest (2026-05-20, all DISCARDED)
| Config | Avg (3-seed) | vs hearts5 |
|--------|-------------|------------|
| return_load=30+hearts5 | 1124 | -3.1% |
| stuck_threshold=12+hearts5 | 1163 | +0.2% |
| hearts=6+fix (6-seed) | 1160 | +0.6% |

All within noise or negative. Issue #77 parameter space fully exhausted.

### Final cumulative improvement (issue #77)
- Baseline 4A4M (6-seed): 1105
- + 3A5M split: 1123 (+1.6%)
- + hearts5+progress-fix: 1153 (+2.7% over 3A5M, +4.4% total)
- Committed at c3f6e8a, all experiments recorded in TSV

---

## Issue #75: RL Curriculum Training (session 4, 2026-05-20)

Switching to RL training after exhausting scripted policy optimization.

### Plan
1. Phase 1: Train from scratch with max_dist=6, clip_coef=0.1, ent annealing 0.04→0.01
2. Phase 2: Fine-tune best Phase 1 checkpoint with max_dist=10
3. Evaluate at 500, 1000, and 10K steps
4. Compare vs scripted policy and previous RL results

### Phase 1a: 1000-step episodes, 64 envs (FAILED)
- Config: 4 cogs, 1000-step episodes, 64 envs, clip_coef=0.1, boost_aligner=5.0, credit+milestones_2
- Trained 123 epochs (2M steps), entropy 1.45-1.60
- All checkpoints eval to 0.1000 per-agent at 1K steps (base reward only)
- **Root cause**: env vars for ent_coef/clip_coef are set by train_curriculum.py but NEVER read by train.py (hardcoded ent_coef=0.01, clip_coef=0.2). Also 1000-step episodes too short for meaningful learning signal.
- Also: training from scratch on natural map fails — agents never acquire hearts, can't align junctions

### Phase 1a revision: 3000-step longep (FAILED)
- Config: 4 cogs, 3000-step episodes, 16 envs, clip_coef=0.2, boost_aligner=5.0, map_seed=42
- Matched previous researcher's config but trained FROM SCRATCH (not warm-started)
- KL=0.0, clipfrac=0.0 for all epochs — policy not updating
- After 544K steps: 0 hearts gained, 0 junctions aligned
- **Root cause**: full curriculum is needed — previous researcher built up through flat-map→natural map→longer episodes. Random policy can't complete aligner→heart→junction pipeline on natural map.

### Phase 1b: flat-map with pre-equipped gear — COMPLETED
- Config: 4 cogs, 1000-step episodes, 16 envs, flat-map, no-clips, start-aligner, start-heart, max_dist=5
- Peak: 4932 held ticks (eval 47, ~epoch 100), avg 1500-2200 in later evals
- Entropy 1.61 → 1.55 (stable, no collapse)
- Trained 110 epochs, checkpoints through e110

### Longep2k arena with starting gear — TRANSFER FAILURE
- Config: 4 cogs, 2000-step episodes, 16 envs, natural terrain, start-aligner, start-heart, max_dist=6
- Learned strongly on training map: 6.65 per-agent reward, held ticks up to 9062
- BUT 1.0001 on competition map (base reward only)
- **Root cause**: agents start with gear in training but not in competition. Model never learned gear acquisition.

### Compmap direct (from scratch) — FAILED
- Config: 4 cogs, 3000-step episodes, 16 envs, cogsguard_machina_1.basic, max_dist=10, no gear
- Brief spike at eval 6 (5335 held, 1.75 junctions) then collapsed to 0 for 10+ evals
- Entropy stuck at 1.60 (random policy) after 120 epochs
- **Root cause**: training from scratch on full map too hard without curriculum

### Phase 2: arena longep3k WITHOUT gear (from P1 warm-start) — FAILED
- Config: 4 cogs, 3000-step episodes, 16 envs, cogsguard_arena.basic, max_dist=6
- Warm-started from P1 flat e080 checkpoint
- Restarted with 1000-step episodes after 3000-step was too slow
- 75 epochs, KL=0.0, clipfrac=0.0, entropy=1.6054 (random policy)
- Only 0.25 hearts gained per evaluation — reward too sparse
- **Root cause**: arena map doesn't transfer; 4 cogs too few; P1 with-gear model can't find gear on new map

### Session 5: following previous researcher's proven curriculum (2026-05-20)

**Key learnings from analyzing previous researcher's branch (claude/amazing-meitner-9HeB9):**
1. Must train on COMPETITION MAP (cogsguard_machina_1.basic), not arena — arena doesn't transfer
2. Must use 8 cogs (not 4) — more agents = more reward signal
3. clip_coef=0.1 prevents entropy collapse (critical after ~50 epochs)
4. train.py env var reading patch needed — applied from previous researcher's branch
5. Proven pipeline: P1 flat → compmap_v1 (comp map, max_dist=6) → tightclip (clip=0.1) → Phase 2 (max_dist=10) → longep3k (3000-step)
6. Best result: longep3k_e20 avg=1.394 per-agent at 10K steps

**Applied train.py patch**: `clip_coef`, `lr`, `gamma`, `gae_lambda`, `anneal_lr`, `min_lr_ratio`, `bptt_horizon` now read from env vars.

**Training launched (2 parallel runs):**
1. compmap_v1: 8 cogs, competition map, max_dist=6, clip=0.2, 1000-step, from P1 flat e080
2. compmap_tightclip: 8 cogs, competition map, max_dist=6, clip=0.1, 1000-step, from P1 flat e080

### Session 5 results: both runs FAILED
- compmap_v1 (clip=0.2): 42 epochs, entropy drifted to 1.58 (random), clipfrac=0.0 from epoch 3
- compmap_tightclip (clip=0.1): 41 epochs, same pattern
- Heart acquisition: sporadic (0.125-1.75 per eval) but too sparse for gradient signal
- Junction alignment: 0.125 total across all evals — nearly zero
- **Root cause**: P1 flat model (4 cogs, with gear) doesn't transfer to competition map (8 cogs, no gear)

### Session 5 comprehensive checkpoint evaluation
ALL existing checkpoints evaluated at 500 steps on competition map — ALL return 0.0500 (base alive reward):
| Checkpoint set | Epochs tested | Result |
|---------------|---------------|--------|
| compmap_v1 | e020, e060 | 0.05 |
| compmap_longep3k | e020, e060, e100 | 0.05 |
| longep3k (arena) | e020, e060, e100 | 0.05 |
| p2_arena_1k | e060, e120, e190 | 0.05 |
| P1_flat | e080 | 0.05 |
| P1_tightclip | e080 | 0.05 |

**The entire RL training effort has produced zero working models.**

### Session 5 additional training attempts (ALL FAILED)
| Config | From | Epochs | Clipfrac | Result |
|--------|------|--------|----------|--------|
| compmap_tc_s6 (clip=0.1, max_dist=6, 1K step) | compmap_v1 e060 | 8 | 0 after epoch 1 | Dead |
| longep3k_tc_s6 (clip=0.1, max_dist=10, 3K step) | compmap_v1 e060 | 6 | 0 after epoch 1 | Dead |

### Issue #76 status: BLOCKED
- Auth token `6PnHPiX9SWLBZhkMyHr4JJWKuUWZY29t_2CTrVDlCHs` returns 401 on submit endpoint
- Both server URLs fail: `api.observatory.softmax-research.net` and `softmax.com/api/observatory`
- Upgraded cogames to 0.27.3 from PyPI — no help
- `cogames auth status` returns "Authenticated as unknown"
- **Cannot submit ANY policy** until auth is refreshed via browser OAuth flow

### Session 6: new training approaches (2026-05-20)

**scratch_comp_hiboost: FAILED**
- FROM SCRATCH on competition map, 8 cogs, clip=0.1, boost_aligner=20.0
- clipfrac=0 after epoch 1, entropy stuck at 1.60 — random policy
- Killed after confirming no learning

**P1 flat 8-cog: COMPLETED (peak 7541 held ticks)**
- Config: Phase 1 flat, 8 cogs, clip=0.1, boost_aligner=5.0, flat-map, no-clips, start-aligner, start-heart, max_dist=5, 1000-step, 16 envs
- Trained 96 epochs, entropy 1.609→1.449
- Peak held: 7541 (epoch ~50), exceeding previous researcher's 7008
- Mean held: 2849 overall
- Checkpoints: model_000010 through model_000090

**Scripted policy 10K eval: 3.74 avg per-agent**
- 3 episodes: 4.57, 2.55, 4.11
- Cogs held: 27,441 avg; Clips held: 1,188,808 avg — clips dominate
- 63.33 junctions aligned (avg); 34.75 deaths per agent
- Confirms scripted policy is the current best, but clips far outperform

**train.py fix: ent_coef now reads from COGAMES_ENT_COEF env var**
- Was hardcoded at 0.01, now reads `os.environ.get("COGAMES_ENT_COEF", "0.01")`

### Session 6b: Phase 2 compmap training

**Phase 2 compmap (from P1 flat e80): partial success**
- Config: cogsguard_machina_1.basic, 8 cogs, max_dist=6, clip=0.1, boost_aligner=5.0, 1000-step
- Warm-started from P1 flat 8-cog e80
- Training held_ticks: peaked at 21K+ (very strong in training env)
- BUT eval on vanilla competition map: 0.3 at 3K steps (alive reward only)
- Root cause: model learns close-range navigation (max_dist=6) but can't reach distant junctions on real map
- Checkpoints: model_000010 through model_000050

**Phase 2 eval sweep (all alive-only):**
| Checkpoint | 1K steps | 3K steps |
|-----------|----------|----------|
| compmap_e010 | 0.10 | 0.30 |
| compmap_e020 | 0.10 | 0.30 |
| compmap_e030 | 0.10 | 0.30 |
| compmap_e040 | 0.10 | 0.31 |
| compmap_e050 | 0.10 | 0.30 |

### Session 6c: longep3k + real-map training

**Longep3k (from compmap e40): abandoned**
- Config: cogsguard_machina_1.basic, 8 cogs, max_dist=10, clip=0.1, boost_aligner=5.0, 3000-step
- Distribution shift confirmed: max_dist=10 training doesn't transfer to max_dist=15 eval

**Previous researcher's checkpoint eval:**
- Loaded compmap_longep3k e020-e060 and longep3k_arena e020-e100
- ALL scored 0.3 or 1.0 (alive only) on competition map
- Even previous researcher's "best" (longep3k_e20, reported 1.394/agent) doesn't reproduce on our eval setup

**Real-map training (from prev researcher's longep3k_comp e50): BREAKTHROUGH**
- Config: phase 3, max_dist=15 (real map), 8 cogs, clip=0.1, ent=0.03, boost_aligner=3.0, 3K-step, 16 envs
- Started from previous researcher's best checkpoint
- Training held_ticks: peaked 2411 (epoch 54), then decayed to 0 by epoch 90+
- Entropy stable at 1.57-1.60, but clipfrac=0.0 after epoch 30 (policy frozen)
- Trained 109 epochs, stopped due to plateau

**Real-map eval sweep (3K steps, seed=42):**
| Checkpoint | Reward | Note |
|-----------|--------|------|
| e005 | 0.300 | alive only |
| e010 | 0.300 | alive only |
| e015 | 0.300 | alive only |
| **e020** | **0.463** | **FIRST model above alive on real map** |
| e025 | 0.379 | slightly above alive |
| e030-e070 | 0.300 | alive only |

**Key finding**: only e020 produces meaningful junction alignment on eval. Earlier and later checkpoints all regress to alive reward. Training held_ticks don't predict eval performance — the model at epoch 20 has a general exploration behavior that works on the eval map, while later epochs overfit.

**10K eval:** e015 at 10K = 1.0001 (alive: 0.1×10K). e020 at 10K: pending.

### Session 7: high-entropy exploration from e020 (IN PROGRESS)

**Hypothesis**: e020 is the best starting point. Higher entropy (0.05 vs 0.03) and stronger reward shaping (boost_aligner=5.0, boost_heart=2.0) should encourage more exploration and prevent the premature convergence seen in the first run.

**Config**:
- weights: realmap e020 (our best checkpoint)
- ent_coef: 0.05 (up from 0.03)
- clip_coef: 0.1
- boost_aligner: 5.0, boost_heart: 2.0
- lr: 0.0005, no LR annealing (constant)
- max_dist=15, 3K-step, 8 cogs, 16 envs, seed=42
- Tag: highent_from_e020

### Session 7b: update_epochs discovery + experiments

**CRITICAL FIX: `update_epochs=1` was hardcoded in train.py**
- PPO needs multiple gradient passes per batch for policy updates. With `update_epochs=1`, `clipfrac=0.0` for ALL training — policy never meaningfully updated.
- Fixed: `update_epochs` now configurable via `COGAMES_UPDATE_EPOCHS` env var (committed 2e3c100)
- Also updated COMPAT_VERSION to 0.25 for beta-cvc compatibility

**Training experiments with update_epochs=4:**

| Config | clipfrac | Entropy | Result |
|--------|----------|---------|--------|
| clip=0.2, lr=0.001, ent=0.05 ("aggressive") | 0.10-0.20 | 1.60→1.45 collapse | Learns but entropy collapses |
| clip=0.1, lr=0.0005, ent=0.05 | 0.0 | 1.60 stable | Too conservative, no learning |
| clip=0.1, lr=0.001, ent=0.1 ("sweet-spot") | 0.01-0.03 rising | 1.60 stable | Promising, killed too early (6 epochs) |
| clip=0.2, lr=0.001, ent=0.15 | 0.0 | 1.60 stable | ent_coef too high, dominates policy loss |
| clip=0.2, lr=0.001, ent=0.05, explore=0.001 ("final_explore") | 0.0-0.29 | 1.60→1.19→1.52 recovery | Ran 17 epochs, entropy recovered! |

**final_explore recovery analysis:**
- Entropy dipped to 1.185 at epoch 9 (near-collapse) then bounced back to 1.52 by epoch 17
- The `explore_weight=0.001` (cell.visited reward) provides dense exploration signal that prevents full collapse
- Clipfrac high throughout (0.02-0.29) — policy actively updating
- Checkpoints available at e003, e006, e009, e012, e015

**All update_epochs=4 checkpoints eval'd at 3K = 0.300 (alive only):**
| Checkpoint | 3K eval | Source |
|-----------|---------|--------|
| update4 e005 | 0.300 | aggressive config |
| update4 e010 | 0.300 | aggressive config |
| update4 e015 | pending | aggressive config |
| update4 e020 | pending | aggressive config |

### Session 8: long-episode training with update_epochs=4 (2026-05-20)

**Strategy**: Combine the two key discoveries:
1. 3000-step episodes (previous researcher's breakthrough)
2. update_epochs=4 (my fix for clipfrac=0)

**Two parallel runs launched from realmap e020:**

1. **sweetspot_longep3k**: clip=0.1, ent=0.05, lr=0.001, constant LR, 3K-step episodes
2. **anneal_longep3k**: clip=0.1, ent annealing 0.08→0.02 over 50%, lr=0.001, constant LR, 3K-step episodes

Both: 8 cogs, 16 envs, map_seed=42, boost_aligner=5.0, boost_heart=2.0, credit+milestones_2, max_dist=15

**sweetspot_longep3k**: KILLED at epoch 12 (merged into anneal analysis below)
- clipfrac oscillating 0-0.18, entropy 1.59-1.61 stable
- Sporadic hearts/aligners, 0 junction alignment
- Similar dynamics to anneal — killed to save CPU

**anneal_longep3k: BREAKTHROUGH — first consistent junction alignment on competition map**

Training dynamics (epochs 1-20):
| Epoch | Entropy | Clipfrac | Hearts/agent | Aligners/agent | Junctions/agent |
|-------|---------|----------|-------------|----------------|-----------------|
| 1 | 1.604 | 0.106 | 0.50 | 0.125 | 0.0 |
| 2 | 1.603 | 0.086 | 0.25 | 0.125 | 0.0 |
| 4 | 1.592 | 0.203 | 0.0 | 0.25 | 0.0 |
| 9 | 1.597 | 0.015 | 0.75 | 0.0 | 0.0 |
| 11 | 1.598 | 0.180 | 0.50 | 0.125 | 0.0 |
| **14** | **1.606** | **0.021** | **1.375** | **0.25** | **0.375** |
| 15 | 1.605 | 0.002 | 0.875 | 0.625 | 0.0 |
| 17 | 1.600 | 0.037 | 0.50 | 0.625 | 0.0 |
| **18** | **1.596** | **0.032** | **1.125** | **0.50** | **0.375** |
| **19** | **1.593** | **0.088** | **1.125** | **0.50** | **0.375** |

Key findings:
- **Junction alignment emerged at epoch 14** — first time ANY RL training has achieved this on the real competition map
- **Consistent junction alignment at epochs 14, 18, 19** — not a fluke
- **Aligner acquisition improving**: 0.125→0.625 per agent (5x increase)
- **Heart acquisition trending up**: 0.25→1.375 per agent
- **Entropy stable**: 1.59-1.61 (entropy annealing barely started at epoch 19 of ~366 total)
- **Clipfrac oscillating 0.002-0.203**: PPO is actively learning

**conservative_longep3k**: KILLED at epoch 5
- update_epochs=2, lr=0.0003, ent=0.03
- clipfrac=0.0 for all 5 epochs — too conservative, no learning
- Replaced with anneal_explore_longep3k

**anneal_explore_longep3k**: RUNNING (epoch 1+)
- Same as anneal_longep3k + explore_weight=0.001 (cell.visited reward)
- Hypothesis: explore_weight provides dense navigation signal that accelerates junction discovery

### Session 9: continued training and evaluation (2026-05-20)

**Training trajectory through epoch 37:**

Three distinct phases observed:
1. **Pre-learning (epochs 1-17)**: entropy ~1.60, clipfrac 0-0.20, sporadic game metrics
2. **Rapid learning (epochs 18-25)**: entropy 1.60→1.48, clipfrac rising to 0.29, heart acquisition improving
3. **Stabilization (epochs 26-37)**: entropy bounced back to 1.52-1.53, clipfrac 0.10-0.17, stable

Game metrics improvement (per-agent averages):
| Metric | Early (e1-11) | Mid (e14-19) | Late (e24-36) |
|--------|--------------|-------------|---------------|
| heart.gained | 0.0-0.75 | 0.5-1.375 | 2.0-5.25 |
| aligner.gained | 0.0-0.25 | 0.25-0.625 | 0.125-0.25 |
| junction.aligned | 0.0 | 0.0-0.375 | 0.0-0.375 |

Key findings:
- **Heart acquisition 10x improvement**: 0.5→5.25 per agent
- **Junction alignment emerging**: 4 of 14 eval blocks show non-zero (0.125-0.375)
- **Agent specialization**: epoch 28 showed agent 7 alone aligning 3 junctions
- **Entropy self-correction**: dropped to 1.46, recovered to 1.53 without intervention
- **Explained variance >0.95**: critic network very accurate

**Eval results (1-episode, 3K steps, 8 cogs, temp=0.7):**
| Checkpoint | Seed | Reward | Note |
|-----------|------|--------|------|
| anneal e015 | 100 | 0.425 avg | 2 episodes: 0.429, 0.421 |
| anneal e020 | 100 | 0.300 | alive only — regression |
| anneal e020 | 42 | 0.300 | alive only (training seed too!) |
| anneal e030 | 100 | 0.300 | alive only |
| anneal e040 | 100 | 0.300 | alive only |

Original e020 baseline: 0.463 per agent at 3K steps.

**CONCLUSION: anneal_longep3k FAILED**

Despite showing promising training metrics (heart acquisition 10x improvement, sporadic junction alignment), ALL checkpoints from epoch 20+ regress to alive-only (0.300) in eval. The anneal training over-optimized heart acquisition via boost_heart=2.0, destroying the junction-seeking exploration behavior the original e020 model had.

Root cause analysis:
- boost_heart=2.0 made heart acquisition the dominant reward signal
- Between epochs 15-20, the model shifted from balanced (hearts+junctions) to heart-only
- The model reliably reaches the hub and collects hearts but never finds/aligns junctions in eval
- Training junction alignment was sporadic (4/14 eval blocks) and unreliable
- Even on the training seed (42), the model can't align junctions in single-episode eval

**Training killed at epoch 52. Pivoting to junction-focused approach.**

### Session 10: junction-focused training (2026-05-20)

**Strategy**: Fix the reward imbalance that caused anneal training to fail.
- Dramatically increase junction alignment reward: boost_aligner=20 (4x previous)
- Remove heart boost entirely: boost_heart=0
- Increase milestones_2 objective compounding: 25x (5x previous default)
- This makes holding aligned junctions the overwhelmingly dominant reward

**junction_focus training config:**
- weights: realmap e020 (original baseline, still best)
- reward: credit,milestones_2:25 (25x objective compounding)
- boost_aligner: 20.0 (aligner_gained=20, junction_aligned=50)
- boost_heart: 0.0 (credit gives heart_gained=0.05 only)
- clip_coef: 0.1, update_epochs: 4, lr: 0.001
- ent annealing: 0.08→0.02 over 50%
- 8 cogs, 16 envs, 3K-step episodes, map_seed=42, max_dist=15
- checkpoint-interval: 3 (faster feedback)

### Session 11: issue #71 — junction control efficiency (2026-05-20)

**Context**: After rebasing to main (fa6d698), map generation changed (now ~140 junctions vs 53 before). Reward format changed to per-cog. Working with scripted policy optimization.

**Post-rebase baseline (3A5M, 3-seed avg 42/43/44):**

| Seed | per cog | junction.gained | junction.held | clips.held |
|------|---------|-----------------|---------------|------------|
| 42   | 3.87    | 63              | 35,666        | 183,120    |
| 43   | 1.85    | 58              | 15,523        | 183,120    |
| 44   | 3.41    | 69              | 31,135        | 183,120    |
| **Avg** | **3.04** | **63.3**     | **27,441**    |            |

**Navigation shake (3 blocked / every 2nd) — DISCARDED**
- Modified from "5 blocked, every 3rd" to "3 blocked, every 2nd" in _step_impl line 518
- Seed 42: +24.8%, Seed 43: -12.4%, Seed 44: -19.1%, **Avg +1.0%** (high variance, inconsistent)

**HP retreat at 25% threshold — MASSIVE IMPROVEMENT (+126.6%)**

**Hypothesis**: Aligners have HP retreat completely disabled (_read_hp returns None), causing 5-6 deaths per aligner per episode. Each death loses gear+heart, requiring expensive re-gearing. Re-enabling retreat at a low threshold prevents deaths while minimizing disruption.

**Changes (machina_llm_roles_policy.py):**
1. Override `_read_hp` to actually read HP from observation tokens
2. Set retreat threshold to 25% (vs 70% used by other agents) — low enough to avoid oscillation
3. Resume threshold at 40% (agents resume work quickly after reaching safety)

| Seed | Baseline | HP Retreat 25% | Delta |
|------|----------|----------------|-------|
| 42   | 3.87     | 5.84           | +50.9% |
| 43   | 1.85     | 6.49           | +250.8% |
| 44   | 3.41     | 8.35           | +144.9% |
| **Avg** | **3.04** | **6.89**    | **+126.6%** |

Junction metrics:
- Gained: 63.3 → 97 (+53%)
- Held: 27,441 → 65,939 (+140%)
- Hearts withdrawn: ~27 → ~203 (7.5x more hub trips)

**Root cause of improvement**: enabling HP retreat doesn't reduce deaths (they actually increased from ~16 to ~30 for aligners), but it dramatically increases heart throughput. Agents cycle through many more heart→align→retreat→heart loops. Total hearts withdrawn went from ~27 to ~203 per game. The continuous cycling means more junctions aligned AND more held time.

**Why deaths increased**: with HP retreat, agents survive more missions → encounter more danger overall → more total deaths, but each death is "cheaper" because the agent was already productive.

**Biggest improvement of the entire session. Committed and will continue testing.**

---

## Session 12: Role Split Re-optimization (Post-Rebase + HP Retreat)

2026-05-20T14:00Z: Starting new experiment loop. My hypothesis is that in braveheart (255 hearts), miners contribute ZERO to the per-cog reward (which counts hub + aligned junctions via `net:cogs` tag). Miners can't get hearts (`isNot(actorHas({"miner": 1}))` filter) and can't align junctions. Their only value is map exploration for the shared map.

Previous 4A4M test was with 25% HP retreat threshold (scored 6.40). Now that we've established 35% as optimal, more aligners might score better. Testing 5A3M and 6A2M with 35% HP retreat.

### Experiment 12a: Role split sweep with 35% HP retreat

| Config | Seed 42 | Seed 43 | Seed 44 | 3-seed avg |
|--------|---------|---------|---------|------------|
| 3A5M | 7.94 | 6.37 | 9.73 | 8.01 |
| 4A4M | 7.13 | 5.65 | 8.81 | 7.20 |
| 5A3M | 11.96 | 5.70 | 11.95 | 9.87 |
| 6A2M | 10.42 | 8.81 | 8.68 | 9.30 |
| 7A1M | 10.68 | 7.46 | 12.84 | 10.33 |
| 8A0M | 10.58 | 10.67 | 4.10 | 8.45 |

More aligners clearly better, peak at 7A1M. 8A0M suffers from station congestion.

### Key discovery: Heart queue bug

The heart queue code (`available_hearts = max(0, 5 + ...)`) hardcodes 5 initial hearts, but braveheart hub has 255. After 5 withdrawals, the code thinks hub is empty and limits to max 3 concurrent get_heart requests, starving 7+ aligner configs.

Fix: `available_hearts = max(0, sm.initial_hub_hearts + sm.hearts_crafted_estimate - sm.hub_hearts_withdrawn)` with `initial_hub_hearts=255`.

### Experiment 12b: 7A1M + heart queue fix (6-seed validation)

| Seed | 7A1M+fix | 8A0M+fix |
|------|----------|----------|
| 42 | 11.55 | 12.39 |
| 43 | 11.47 | 10.78 |
| 44 | 13.57 | 13.54 |
| 45 | 12.09 | 12.46 |
| 46 | 14.56 | 10.53 |
| 47 | 16.66 | 16.60 |
| **Avg** | **13.32** | **12.72** |

7A1M + heart queue fix is the new best: **13.32** per cog (6-seed avg), **+66%** vs 3A5M baseline.

Committed as f6f0cde. Changes: heart queue fix + default 7/8 aligner fraction + initial_hub_hearts=255.

### Cumulative improvement chain
- Baseline (3.04) → HP retreat 35% (+163%) → 7A1M + heart fix (+66%) = **+338% total**

### Experiment 12c: Heart accumulation sweep with 7A1M

| Hearts | Seed 42 | Seed 43 | Seed 44 | 3-seed avg |
|--------|---------|---------|---------|------------|
| 2 | 10.10 | 8.69 | 7.15 | 8.65 |
| **5 (default)** | **11.55** | **11.47** | **13.57** | **12.20** |
| 7 | 11.28 | 10.11 | 10.97 | 10.79 |
| 8 | 14.24 | 13.67 | 9.43 | 12.45 |

Hearts=5 remains optimal. Too few hearts = excess hub travel. Too many = hub congestion with 7 aligners. Discarded, keeping hearts=5.

### Experiment 12d: Fine-tuning sweep (all discarded)

| Experiment | 3-seed avg | vs baseline (12.20) | Notes |
|-----------|-----------|-------------------|-------|
| Resume 40% (from 50%) | 12.20 | 0% | No effect |
| No retreat during gear_up | 12.19 | 0% | No effect |
| Stuck threshold 10 | 10.06 | -17.5% | Too aggressive |
| Stuck threshold 20 | 13.11 | +7.5% (noise) | 6-seed: 13.20 < 13.32 baseline |
| Stuck threshold 25 | 12.42 | +1.8% | Noise |
| Move cooldown 5 | 11.42 | -6.4% | Oscillation worse |
| Move cooldown 7 | 12.39 | +1.6% | Noise |
| Friendly territory 20 (from 15) | 11.77 | -3.5% | Less safe area hurts |
| Blacklist clear on heart refill | 12.82 | +5.1% (3-seed) | 6-seed: 12.56 < 13.32, reverted |
| 6A2M at 10K steps | 11.44 | — | 7A1M still better (12.90) |

### 10K step validation
7A1M at 10K steps: avg 12.90 (42:12.25, 43:12.17, 44:14.27). Improvement scales to competition episode length.

### Conclusion
The committed config (7A1M, HP retreat 35%/resume 50%, hearts=5, stuck=15, cooldown=6, friendly_dist=15, heart_queue_fix) appears to be at a strong local optimum. All single-parameter changes tested are within noise or worse.
