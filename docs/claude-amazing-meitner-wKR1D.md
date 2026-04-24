# Experiment Report: claude/amazing-meitner-wKR1D

## Issue: #40 — Mining throughput gap

2026-04-24T00:00: autoresearch starting, my plan is to continue improving mining throughput. The 10x gap vs RL policies (1456 deposits vs ~14,000 at 10k steps) is still open. Previous researchers fixed deposit stuck loops, extractor depletion detection, and hub diversification. The remaining bottleneck per the director (Session 13): "a new freeze emerges at ~5k steps (73 junctions, then plateau)" caused by:
1. All nearby extractors deplete and miners must explore further — exploration is slow
2. Hub-weighted extractor selection keeps miners close but limits resource diversity
3. Single hub creates a bottleneck for deposits (all miners converge)

My plan: first run baseline, then profile where miners spend their time at 5k-10k steps to identify the specific freeze point.

2026-04-24T00:01: starting to run baseline

2026-04-24T06:30: CRITICAL FINDING — CrossRoleState was missing 9 fields required by MinerSkillImpl (steps_since_last_move, move_cooldowns, depleted_extractors, etc.). This caused ALL agents to return noop every step since the issue-44 merge. CrossRolePolicy has been completely broken. Added the missing fields — agents now functional.

2026-04-24T06:50: running proper baseline with CrossRoleState fix ONLY (no mining improvements). All mining-specific changes (depleted_extractors tracking, active_extractors fast-path, hub tether increase, explore timeout) reverted. This isolates the CrossRoleState fix as the baseline.

### Baseline Results (CrossRoleState fix only, no mining changes)

| Seed | Steps | Score/cog | Junctions | Total Deposits | Hearts | Deaths |
|------|-------|-----------|-----------|----------------|--------|--------|
| 42   | 10000 | 2.89      | 46        | 2134 (C=540 Ge=530 Si=550 Ox=514) | 5 | 2 |
| 123  | 10000 | 1.47      | 4         | 160 (C=60 Ge=20 Si=30 Ox=50) | 4 | 1 |
| 456  | 10000 | 2.01      | 25        | 2100 (C=520 Ge=520 Si=520 Ox=540) | 4 | 6 |
| **Avg** | | **2.12** | **25** | **1465** | **4.3** | **3** |

### Comparison: mining fixes vs baseline

| Variant | Seed 42 Score | Seed 42 Deposits |
|---------|---------------|------------------|
| Baseline (CrossRoleState fix only) | 2.89 | 2134 |
| All mining fixes (818a5bb) | 2.42 | 1910 |

**Conclusion: mining fixes HURT performance (-16% reward, -10% deposits).** The depleted_extractors tracking, explore timeout, and hub tether increase are counterproductive. Discarding them.

2026-04-24T07:00: seed 42 baseline done. 2.89/cog with 2134 deposits and 46 junctions. 

2026-04-24T07:10: all 3 seeds done. Seed 123 is a "bad seed" with severe congestion (agents stuck 5000+ steps, max_steps_without_motion up to 5890). Seed 456 has high mortality (6 deaths). Average across seeds: 2.12/cog. Baseline established.

2026-04-24T07:11: DISCARDING mining fixes. The baseline without them is better. The CrossRoleState field fix alone is the only "keep" from this session. Previous best was 2.53/cog at 10k (seed 42), so our 2.89/cog is a new high. Next experiment: investigate why seed 123 has such severe congestion (5A/3M might be suboptimal — too many agents competing for gear stations).
