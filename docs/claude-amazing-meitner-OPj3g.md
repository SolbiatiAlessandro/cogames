# Autoresearch: Issue #67 — Aligner Throughput Bottleneck

Branch: `claude/amazing-meitner-OPj3g`

## Context
After the gear contamination fix (#64, +15.2%), mining is no longer the bottleneck. Resource surpluses are 300-650 per element, but hearts withdrawn is only 20-31 out of maximum potential 69-97. The constraint is now aligner throughput: how fast aligners can cycle hub→junction→hub.

## 2026-05-08T10:30: autoresearch starting

My plan is to improve aligner throughput by attacking the main bottleneck areas:

1. **Hub wait time**: Aligners currently wait up to 6 ticks for additional hearts (no_progress_on_target_steps < 6). This creates idle time, especially with 4 aligners competing.
2. **Heart carry strategy**: Aligners try to accumulate 3-4 hearts before leaving hub. This may cause congestion.
3. **Junction selection**: `_cascade_priority_target` uses `travel + hub_dist * 0.2` scoring. Could be more aggressive about nearest-first.
4. **JUNCTION_ALIGN_DISTANCE**: Currently 25, could increase to expand alignable territory.

Key metrics to track:
- hearts_withdrawn (target: >40, baseline: ~25)
- mission_reward (target: >3.8, baseline: ~3.282)
- junction.held (proxy for alignment speed)

## 2026-05-08T10:30: starting to run baseline

## 2026-05-08T17:47: baseline result is:

Note: Using PyPI mettagrid 0.15.0 (not git commit version). Reward scale differs from previous experiments but relative comparisons are valid.

| Seed | Total Reward | Avg/Agent | Hearts Gained | Hearts Used | Junctions Aligned |
|------|-------------|-----------|---------------|-------------|-------------------|
| 42 | 1040.43 | 130.05 | 61 | 50 | 50 |
| 123 | 1071.49 | 133.94 | 69 | 55 | 55 |
| 7 | 1103.23 | 137.90 | 70 | 59 | 59 |
| 99 | 1081.57 | 135.20 | 63 | 54 | 54 |
| 555 | 1184.05 | 148.01 | 68 | 59 | 59 |
| **Avg** | **1096.15** | **137.02** | **66.2** | **55.4** | **55.4** |

Key observations:
- `junction.aligned_by_agent` == `heart.lost` in all seeds (each alignment costs 1 heart)
- Average 55.4 junctions aligned per 3000 steps across 4 aligners
- That's ~13.8 junctions per aligner per 3000 steps, or ~1 alignment every 217 steps

## 2026-05-08T17:50: starting new experiment loop

**Experiment 1: Fast-cycle aligners — reduce heart accumulation**

Hypothesis: Aligners currently accumulate up to 4 hearts before leaving hub, waiting up to 6 ticks for each additional heart. With 4 aligners competing for hearts, this creates congestion. By making them leave with 1 heart immediately (max 2 if already near hub, only 2 ticks patience), each aligner cycles faster hub→junction→hub, increasing total throughput.

Changes:
1. `aligner_agent.py:788` — `want_more_hearts` threshold: `< 3` → `< 2`
2. `machina_llm_roles_policy.py:368` — Heart accumulation: `< 4` → `< 2`, patience: `< 6` → `< 2`
3. `machina_llm_roles_policy.py:283,305` — Override heart thresholds: `< 4` → `< 2`

Results (5-seed avg):

| Seed | Total Reward | Baseline | Change | Hearts Gained | Junctions Aligned |
|------|-------------|----------|--------|---------------|-------------------|
| 42 | 906.68 | 1040.43 | -12.9% | 50 | 46 |
| 123 | 1050.90 | 1071.49 | -1.9% | 59 | 55 |
| 7 | 1146.89 | 1103.23 | +4.0% | 70 | 60 |
| 99 | 1114.49 | 1081.57 | +3.0% | 66 | 55 |
| 555 | 1199.08 | 1184.05 | +1.3% | 71 | 61 |
| **Avg** | **1083.61** | **1096.15** | **-1.1%** | **63.2** | **55.4** |

**DISCARD**: Regression. Reducing heart accumulation didn't help — junctions aligned stayed the same (55.4), but hearts gained dropped from 66.2 to 63.2. Travel time dominates, so carrying more hearts per trip is better. The bottleneck is not hub congestion.

## Experiment 2: Fix junction alignment distance mismatch

Hypothesis: Policy uses `_JUNCTION_ALIGN_DISTANCE=25` for cascade check in `_is_alignable()`, but game engine uses `CvCConfig.JUNCTION_ALIGN_DISTANCE=15`. This means aligners travel to junctions in the 16-25 range from friendly junctions where cascade alignment will fail (heart not consumed, but time wasted on travel + timeout). Fixing to 15 should eliminate these wasted trips.

Additionally, separate exploration frontier to a new `_JUNCTION_EXPLORE_DISTANCE=25` constant so agents still scout broadly but only target truly alignable junctions.

Changes:
1. `aligner_agent.py:25` — `_JUNCTION_ALIGN_DISTANCE = 25` → `15`
2. `aligner_agent.py:26` — New `_JUNCTION_EXPLORE_DISTANCE = 25`
3. `aligner_agent.py:653` — `_alignment_frontier_cells` uses `_JUNCTION_EXPLORE_DISTANCE` for search radius
