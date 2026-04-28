# Experiment Log: claude-amazing-meitner-ZmdFf

## Issue: #50 — Close the 21% gap to #1: per-agent alignment efficiency tuning

## 2026-04-28T05:25: autoresearch starting

Continuing from mjSjH session. Current best is 214.68 avg (10-seed, 42-51, 1000 steps).
Branch has all prior improvements: hub_dist=0.2, max_hearts=4, 3A+5M static IDs, BFS cooldown bypass, phantom aligner station fix.

My plan:
1. Fix SharedMap coordinate contamination in `_is_alignable` (phantom hubs make distant junctions appear alignable)
2. Fix phantom hubs in `_get_heart` navigation (agents navigate to phantom hub positions)
3. Improve junction target selection with BFS-aware scoring
4. Explore multi-heart batch optimization

## 2026-04-28T05:28: baseline confirmed

10-seed avg = 214.68
Seeds: 237.38/202.74/210.19/243.61/231.44/188.33/230.77/231.91/179.50/190.93
Weakest: seed 50 (179.50), seed 47 (188.33), seed 51 (190.93)
Strongest: seed 45 (243.61), seed 42 (237.38), seed 46 (231.44)

## 2026-04-28T05:35: Experiment 1 — Verified hubs for aligner

**Hypothesis**: SharedMap coordinate contamination affects hubs like it affected aligner stations. Agents with different spawn points write hub coords in their own frame, creating phantom hubs. _is_alignable, _get_heart, _cascade_priority_target, and near_hub checks all use shared known_hubs. Fix: add per-agent verified_hubs.

**Result: 240.38 avg (+12.0% over 214.68 baseline) — KEEP**
Seeds: 198/226/240/252/224/218/257/255/269/265

Per-seed analysis:
- Seed 50: 179→269 (+49.9%) — phantom hubs were sending aligners to wrong positions
- Seed 51: 191→265 (+38.6%) — same root cause
- Seed 47: 188→218 (+15.7%) — significant improvement
- Seed 42: 237→198 (-16.6%) — regression, phantom hubs may have accidentally helped on this seed
- Seed 46: 231→224 (-3.1%) — slight regression

Key insight: The phantom hub contamination was the DOMINANT factor on weak seeds. These seeds had spawn configurations where coordinate frame differences were largest, causing aligners to navigate to phantom hub positions and waste hundreds of steps.

The seed 42 regression is acceptable given the massive overall improvement. The net effect is +25.7 reward per episode.

## 2026-04-28T05:42: Experiment 2 — Verified hubs for miners

Extended phantom hub fix to miners. Tried two variants:

**Variant A: verified_hubs + verified_extractors** → 247.89 avg
- Seeds 50/51 regressed badly (269→197, 265→215)
- Miners benefit from shared extractor locations — verified extractors is too restrictive

**Variant B: verified_hubs only (no extractors)** → 247.22 avg (+2.8% over aligner-only)
- Seeds: 254/241/270/282/209/229/264/254/244/225
- Seed 42 recovered: 198→254 (+28.3%)
- Seeds 50/51 still regressed from aligner-only (269→244, 265→225) but less severely
- Overall avg improved: 240.38→247.22

**Keep**: variant B (verified_hubs only). Combined aligner+miner fix gives +15.2% over baseline.

## 2026-04-28T05:55: Experiment 3 — stuck_threshold 20→15

**Hypothesis**: With verified hubs fixing phantom navigation, agents now reach their targets faster. The stuck_threshold (steps before abandoning a skill) can be tightened from 20 to 15 — agents should switch skills sooner when genuinely stuck rather than waiting due to phantom-hub-induced confusion.

**Result: 251.36 avg (+1.7% over 247.22, +17.1% over baseline) — KEEP**
Seeds: 256/254/265/284/216/234/274/265/238/228

Per-seed analysis:
- Seed 45: 282→284 (stable)
- Seed 48: 254→265 (+4.3%) — faster skill switching helps
- Seed 50: 244→238 (-2.5%) — slight regression
- Seed 42: 254→256 (+0.8%) — stable
- Overall variance reduced: agents abandon dead-end skills sooner

## 2026-04-28T06:10: Experiment 4 — Parameter tuning (discarded)

Tried three parameter variations on top of the 251.36 baseline:

**4a: Alignment distances 25/20 → 30/25** → 245.54 avg — DISCARD
- Wider alignment radius caused aligners to attempt junctions they couldn't efficiently reach
- Net regression of -2.3%

**4b: hub_dist 0.2 → 0.15** → 251.42 avg — DISCARD
- Negligible change (+0.02%), within noise
- Tighter hub proximity didn't help; 0.2 already appropriate

**4c: stuck_threshold 15 → 12** → 244.90 avg — DISCARD
- Too aggressive: agents abandon skills before completing them
- -2.6% regression, especially on seeds needing longer navigation

**Conclusion**: stuck_threshold=15 is the sweet spot. Parameter tuning shows diminishing returns — need structural improvements for further gains.

## 2026-04-28T06:25: Seed analysis

Investigated weak seed 47 (220.61) vs strong seed 42 (251.14):
- Seed 47: 754 move failures, 44 junctions aligned
- Seed 42: 452 move failures
- High move failure count on seed 47 suggests map geometry creates bottlenecks

## Current best: 251.36 avg (10-seed, 1000 steps) — +17.1% over baseline 214.68
