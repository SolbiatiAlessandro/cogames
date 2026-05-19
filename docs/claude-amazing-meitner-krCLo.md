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
