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

## Experiment 2: 3A/5M vs 5A/3M configuration

2026-04-24T07:15: Hypothesis — the default 3A/5M config (more miners) might be better than 5A/3M because: (1) more miners = more deposits, (2) fewer aligners still cover junction needs since aligners are already efficient, (3) the 5A/3M config was tested before by another researcher who found -26.3% vs 4A/4M, but that was before the CrossRoleState fix so results may differ now. Also, the tournament defaults to 3A/5M, so optimizing for that config is more directly applicable.

### 3A/5M Results

| Config | Seed | Score/cog | Junctions | Deposits | Deaths |
|--------|------|-----------|-----------|----------|--------|
| 5A/3M (baseline) | 42 | 2.89 | 46 | 2134 | 2 |
| 5A/3M (baseline) | 456 | 2.01 | 25 | 2100 | 6 |
| 3A/5M | 42 | 2.05 | 34 | 1610 | 2 |
| 3A/5M | 456 | 2.17 | 24 | 1788 | 89 |

**Conclusion: 3A/5M is WORSE.** 5A/3M wins on both seeds. Seed 42: -29% reward, -25% deposits. Seed 456: similar junctions but 89 deaths vs 6 (miners die constantly). More miners creates extractor/hub congestion and doesn't produce more deposits. The junction advantage of 5 aligners (46 vs 34) is the main reward driver. DISCARDING 3A/5M.

2026-04-24T07:40: Seed 123 diagnostic revealed the root cause of congestion: 5 agents trying to gear up as aligners at a single aligner station, creating a bottleneck. Agents 0,1,3,4 accumulate 8+ gear_up failures each. The conversion ceiling (10 failures before converting aligner→miner) wastes ~2000 steps per agent.

## Experiment 3: Faster gear-up failure conversion

2026-04-24T07:45: Hypothesis — reducing the gear_up_failures_total threshold from 10 to 4 will reduce wasted steps on gear station contention. Agents that can't reach the aligner station quickly convert to miners and start being productive earlier. This should especially help seed 123 where 4 agents are stuck in the gear_up retry loop.

### Results

| Seed | Baseline | Faster-gear (10→4) | Delta |
|------|----------|-------------------|-------|
| 42   | 2.89     | 2.24              | -22%  |
| 123  | 1.47     | 1.47              | 0%    |
| 456  | 2.01     | 2.37              | +18%  |

**Conclusion: DISCARDED.** Seed 42 regression (-22%) is catastrophic: drops from 46→21 junctions because converting aligners to miners too early removes productive aligners on maps where the station IS reachable. Seed 123 unchanged (problem is deeper). Seed 456 improves but net negative. REVERTED.

2026-04-24T08:15: Key learning — aligners are the primary reward driver, not miners. The 5A/3M configuration works because junctions drive reward. Any change that reduces effective aligner count hurts badly. Mining throughput improvements must NOT come at the cost of alignment capacity.

## Experiment 4: return_load=40 (double batch size)

2026-04-24T08:16: Hypothesis — increasing return_load from 20 to 40 doubles the cargo per trip. With only 3 miners, each trip's overhead (walking to extractor, walking back to hub) is significant. Doubling the payload per trip should increase net deposits. Previous researcher found return_load=20 was -28.3% at 3k steps with broken CrossRoleState, so that data is unreliable. Testing fresh.

### Results

| Config | Seed | Score/cog | Junctions | Deposits | Deaths |
|--------|------|-----------|-----------|----------|--------|
| baseline (RL=20) | 42 | 2.89 | 46 | 2134 | 2 |
| baseline (RL=20) | 123 | 1.47 | 4 | 160 | 1 |
| baseline (RL=20) | 456 | 2.01 | 25 | 2100 | 6 |
| return_load=40 | 42 | 2.10 | 29 | 2840 | 5 |
| return_load=40 | 123 | 1.44 | 4 | 840 | 1 |
| return_load=40 | 456 | 3.22 | 51 | 2780 | 49 |

**Average: baseline 2.12/cog → return_load=40 2.25/cog (+6%).**
**Deposits: 1465 → 2153 (+47%) — consistent improvement across all seeds.**

**Conclusion: DISCARDED.** Deposits consistently improved (+33-425%) but reward is mixed (1/3 improved, 1/3 flat, 1/3 worse). The +6% average reward is within noise given the massive variance (seed 42: -27%, seed 456: +60%). The deposit pipeline improvement is real but doesn't translate reliably to reward because junctions, not deposits, drive score. Moving to aligner efficiency improvements instead.

2026-04-24T08:30: Key insight from code review — the policy uses `_JUNCTION_ALIGN_DISTANCE = 20` but the game engine (`CvCConfig.JUNCTION_ALIGN_DISTANCE`) uses 15. Aligners incorrectly consider junctions at distance 16-20 from friendly junctions as alignable. This wastes aligner time traveling to junctions they can't actually align. This is a bug fix, not a tuning change.

## Experiment 5: Fix _JUNCTION_ALIGN_DISTANCE (20→15)

2026-04-24T08:35: Hypothesis — aligner_agent.py uses `_JUNCTION_ALIGN_DISTANCE = 20` but the game engine (CvCConfig) uses 15. This means the policy incorrectly considers junctions at distance 16-20 from friendly junctions as alignable. Aligners waste time traveling to these junctions, attempting alignment, failing, and getting the junction blacklisted. Fix: change 20→15 to match game config.

### Results

| Config | Seed | Score/cog | Junctions | Deposits | Deaths |
|--------|------|-----------|-----------|----------|--------|
| baseline | 42 | 2.89 | 46 | 2134 | 2 |
| baseline | 456 | 2.01 | 25 | 2100 | 6 |
| junction fix | 42 | **3.04** | **54** | 2774 | 6 |
| junction fix | 456 | **2.04** | **38** | 2148 | 17 |

**Average: baseline 2.45/cog → junction fix 2.54/cog (+3.7%). Junctions: 35.5 → 46 (+30%).**

**Conclusion: KEEP.** Both seeds improved. Seed 42 new all-time best: 3.04/cog. Junctions consistently improved on both seeds (+17%, +52%). The fix prevents wasted aligner trips to non-alignable junctions and prevents false blacklisting of junctions that could become alignable as the network expands. Committed as e30dfff.

## Experiment 6: Reduce cascade_priority_target hub_dist weight (0.7→0.3)

2026-04-24T09:00: Hypothesis — the `_cascade_priority_target` scoring `travel + hub_dist * 0.7` heavily favors junctions near the hub. Since clips is a PvE faction (not a real opponent), alignment speed matters more than defensive positioning. Reducing the weight to 0.3 lets aligners pick closer junctions even if they're farther from hub, reducing travel time per alignment and increasing alignment throughput.

### Results

| Config | Seed | Score/cog | Junctions | Deposits | Deaths |
|--------|------|-----------|-----------|----------|--------|
| junction fix (0.7) | 42 | 3.04 | 54 | 2774 | 6 |
| junction fix (0.7) | 456 | 2.04 | 38 | 2148 | 17 |
| hub_dist=0.3 | 42 | 2.77 | 50 | 1520 | 2 |
| hub_dist=0.3 | 456 | 2.04 | 38 | 2092 | 17 |

**Conclusion: DISCARDED.** Seed 42 regressed significantly (-9% reward). Deposits crashed from 2774 to 1520 (-45%). Seed 456 unchanged. The 0.7 weight keeps aligners near the hub where their aligned junctions are protected from clips' scrambling and contribute more to territory control (healing for miners). Reverted to 0.7.

2026-04-24T09:30: Key learning — hub proximity matters for junctions because: (1) clips scramble junctions near their network, (2) territory control from hub+junctions heals nearby agents, (3) junctions aligned early near hub accumulate more hold-time for scoring. The 0.7 weight is well-tuned.

## Experiment 7: Junction fix + return_load=40 (combined)

2026-04-24T09:35: Hypothesis — the junction fix (exp 5, KEEP) improved alignment accuracy. return_load=40 (exp 4, discarded alone) improved deposits by +33-47%. Perhaps combining them compounds the benefits: better alignment targeting + more hearts from higher deposits. The junction fix might also mitigate the seed 42 regression seen with return_load=40 alone (since aligners are now more accurate, they don't waste time on false targets).

### Results

| Config | Seed | Score/cog | Junctions | Deposits | Deaths |
|--------|------|-----------|-----------|----------|--------|
| junction fix only | 42 | 3.04 | 54 | 2774 | 6 |
| junction fix only | 456 | 2.04 | 38 | 2148 | 17 |
| combined (jf+rl40) | 42 | 2.84 | 54 | 3430 | 11 |
| combined (jf+rl40) | 123 | 1.44 | 4 | 840 | 1 |
| combined (jf+rl40) | 456 | 2.71 | 40 | 2310 | 33 |

**Conclusion: DISCARDED.** Mixed results. Seed 456 improved +33% but seed 42 (our best, 3.04) regressed -7%. Miner mortality nearly doubled on both seeds (11 vs 6, 33 vs 17) because miners carry 40 cargo and stay away from hub longer, losing HP. The extra deposits don't compensate for the increased downtime from deaths (respawn + re-gear). return_load=40 definitively hurts on maps where miners face more combat/hazard exposure.

2026-04-24T10:00: CRITICAL FINDING — the `get_heart_cooldown_steps` field is NEVER set to a positive value in the entire codebase. It's initialized to 0 and only ever reset to 0 (lines 678, 693, 713). This means the entire heart cooldown system is dead code:
- `hub_on_cooldown` is always False
- `hub_depleted` is always False
- The periodic hub return interval (200 steps) never triggers
- The fast-path "explore when hub depleted" never triggers
- The LLM override "get_heart → explore when depleted" never triggers
The only working throttle on heart acquisition is the `agents_getting_hearts` set-based queue management.

## Experiment 8: Fix heart cooldown system
