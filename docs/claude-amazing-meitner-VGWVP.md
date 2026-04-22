# Experiment Log: Issue #46 — v37/v38 regression fix

## Branch: claude/amazing-meitner-VGWVP

2026-04-22 00:00: autoresearch starting, my plan is to:
1. Validate that the current branch code (which has all session 13+14 fixes merged) works correctly offline
2. Run baseline with 500 steps, 8 cogs, seed 42 (expect ~8+ total reward)
3. Upload the policy to Softmax as lessandro-scripted-v39
4. Monitor online match results for crashes and score improvements over v32 (16.87)
5. If baseline is solid, explore further improvements to maximize reward

The root cause of the v37/v38 regression was uploading from a branch that was missing:
- hub_deposits_total tracking
- Aligner extractor sharing
- Gear-up hazard fallback fixes
- Death-detected gear reset
- Correct role allocation (scripted_miners=True, num_aligners=min(4, n_agents//2))

This branch has all those fixes merged via session 15 director commit.

2026-04-22 17:25: starting to run baseline

2026-04-22 17:27: baseline results:
- **500 steps, 8 cogs, seed 42**: total_reward=34.26, avg_per_agent=4.28, 17 hearts, 4 miners + 4 aligners
- **3000 steps, 8 cogs, seed 42**: total_reward=789.18, avg_per_agent=98.65, 47 hearts, 43 junctions aligned
- **500 steps, 4 cogs, seed 42**: total_reward=18.26, avg_per_agent=4.56, 18 hearts, 2 miners + 2 aligners

All results are excellent. The 4-agent scenario confirms the role allocation fix works (2 miners + 2 aligners, not 0 miners + 4 aligners as in v37).

The 500-step 8-cog result (34.26) far exceeds the issue's ~8+ threshold.
Next: upload to Softmax as lessandro-scripted-v39.

2026-04-22 17:30: uploaded lessandro-scripted-v39:v1 to beta-cvc qualifying pool
- Policy version ID: e398e343-b369-4103-b023-38e4e5d9dc2d
- Branch: claude/amazing-meitner-VGWVP (commit 15a8c95 + baseline results abf6d4e)
- Contains all session 13+14 fixes + issue #44 improvements
- Correct role allocation: scripted_miners=True, num_aligners=min(4, n_agents//2), num_scouts=0

Next: monitor online results, then explore further improvements while we wait.

2026-04-22 17:33: starting new experiment loop, in this experiment I want to try hub approach diversification.

Analysis of 3000-step run logs reveals 363 stuck/stale events, of which **294 (81%)** are `deposit_to_hub exited as stale`. Miners all approach the hub from the nearest side, creating congestion when 4 miners try to deposit simultaneously.

**Hypothesis**: If each miner approaches the hub from a different direction (based on agent_id), congestion will decrease and deposit throughput will improve, leading to more mine-deposit cycles and higher total reward.

**Implementation**: Modify `_deposit_to_hub` to sort approach cells with an agent-id-based preference for different hub sides, distributing miners around the hub perimeter.

2026-04-22 17:36: experiment results for hub approach diversification:
- **500 steps, 8 cogs, seed 42**: 38.64 (+12.8%) — hearts 17→23 (+35%)
- **3000 steps, 8 cogs, seed 42**: 839.35 (+6.4%) — deposit stale 294→148 (50% reduction)
- **3000 steps, 8 cogs, seed 123**: 567.03 (neutral on this seed)

This is a good result. Keeping the change. Resource throughput up 50-78% across elements.

2026-04-22 17:39: starting new experiment loop. 148 deposit stale exits remain. My hypothesis is that increasing the stale tolerance for deposits (from 20 to 40 steps) will let miners wait out congestion rather than cycling through stale→explore→deposit loops. The explore cycle wastes ~30+ steps per cycle.

2026-04-22 17:44: deposit side rotation results:
- **3000 steps, 8 cogs, seed 42**: 884.93 (+12.1% vs baseline, +5.4% vs diversify-only)
- Hearts: 50 (up from 45). max_steps_without_motion: 57 (down from 159).
- Deposit stale exits: 240 (higher count but each triggers a side change, so deposits succeed faster overall)

2026-04-22 17:46: deposit patience experiment (1.5x stale threshold): **regression** to 718.52
- Reverted immediately. Longer patience makes miners wait at congested side longer, not better.
- The 20-step stale + rotation is the optimal pattern.

2026-04-22 17:49: starting new experiment: trying return_load=30 (down from 40). Hypothesis: more frequent, lighter deposits will spread hub access over time, reducing congestion spikes when 4 miners all finish mining at similar times.

2026-04-22 17:50: return_load=30 results: **regression** to 629.30. Travel time overhead too costly. Discarded.

2026-04-22 18:00: Analyzed event distribution from 3000-step run. **240 out of 305 deposit attempts exit as stale** (79% failure rate). Each wastes 20 steps = 4800 agent-steps wasted total. Stale exits occur when miner is adjacent to hub but deposit move doesn't succeed within the stale threshold.

Tried approaches:
- **Deposit queue coordination via SharedMap**: Added `miners_depositing` set to SharedMap. Queue never triggers — with 4 miners and hub diversification, rarely 2+ depositing simultaneously. Reverted.
- **Deposit stale backoff (explore after 3 consecutive stale exits)**: Reduced deposit stale from 240→20 but increased mine stale 30→71. Net regression to 878.57. Explore detours waste more time than retry cycles. Reverted.
- **10-step deposit stale threshold**: Too aggressive — 782.40 regression. Miners don't have enough time to complete deposit before being rotated away.
- **5 miners + 3 aligners**: Regression to 608.62. Not enough aligners.
- **3 miners + 5 aligners**: Slight regression to 847.72. Mining throughput becomes the bottleneck.

2026-04-22 18:26: **faster deposit side rotation (15-step stale threshold)** — **NEW BEST**
- Reduced deposit stale threshold from 20 to 15 steps (3/4 of stuck_threshold) specifically for deposit_to_hub
- Miners rotate to next hub side after 15 steps of no progress instead of 20, finding clear sides ~25% faster
- **3000 steps seed 42**: 893.72 (+1.0% vs 884.93 prev best). Hearts 52, deposit stale 186 (vs 240)
- **3000 steps seed 123**: 651.01 (+14.8% vs 567.03). Major improvement on this seed.
- **500 steps seed 42**: 37.42 (+9.2% vs 34.26). Hearts 20 (vs 17).
