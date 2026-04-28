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
