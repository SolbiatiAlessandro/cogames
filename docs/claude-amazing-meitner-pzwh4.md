# Experiment Log: claude/amazing-meitner-pzwh4

## Issue: #46 - v37/v38 regression fix + continued improvement

2026-04-23 09:00: autoresearch starting, my plan is to:
1. Run baseline on current code (session 15, commit 15a8c95)
2. Analyze online performance gap (v42=21.78 vs top=41.10, ~53% of best)
3. Focus on highest-leverage improvements to close the gap
4. Key areas: mining throughput, navigation efficiency, agent coordination

Current online standings:
- Our best: v42 at #90 (score 21.78)
- Top: Paz-Bot-9000:v47 at #1 (score 41.10)
- Gap: ~2x improvement needed

2026-04-23 09:01: starting to run baseline

2026-04-23 09:15: Baseline at 10k steps = 3681.91 (seed 42), 53 hearts, 48 junctions aligned.
Diagnosed critical deposit stuck issue: miners adjacent to hub but unable to deposit (stale on target).
Root cause: `_scripted_skill_choice` didn't handle `was_stale` when cargo is full — only `was_stuck`.
Miners cycled: deposit_to_hub(20 steps) → stale exit → deposit_to_hub → stale exit, forever.

2026-04-23 09:45: Fix v41 - deposit stuck + extractor depletion

Changes:
1. Handle stale exits same as stuck in scripted_skill_choice when cargo is full
2. Track consecutive_stuck_exits to scale explore duration after repeated failures
3. Mark extractors as depleted (depleted_extractors set) instead of removing from known_extractors
4. Add explore timeout (stuck_threshold * 3 = 60 steps) to prevent infinite explore loops
5. Skip explore→stuck redirect when explore itself timed out (was_explore_exit check)
6. Faster deposit stale detection: max(6, stuck_threshold//3) vs full stuck_threshold

Results:
- Mining throughput: 42 → 97 successful deposits (+131%)
- Resource production: 2.3x more resources deposited
- hearts_crafted_estimate: 58 → 128 (+121%)
- Total reward: 3681.91 → 3688.98 (+0.2%) — small because junctions are the bottleneck
- 3000-step seed 42: 937.61 → 944.68 (+0.7%)
- No regressions across seeds 42, 123, 7
