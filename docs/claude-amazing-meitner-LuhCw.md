# Experiment Log: claude/amazing-meitner-LuhCw

## Issue: #61 - Agent longevity: survive 8000+ steps in 10k-step online matches

2026-05-04T08:00: autoresearch starting. My plan is to improve agent survival in 10k-step games.

Key context from prior work (eTn0X branch, issue #61 comment):
- HP retreat 40%/70% hysteresis + stuck_threshold=30 = best result (+6.5% reward, -41% deaths)
- v8 online (50%/85% thresholds) was too conservative → scored 31.53 vs v1's 35.00
- v11 (with eTn0X improvements) awaiting online evaluation
- Suggested next: stuck_threshold=40, return_load tuning, explore speed improvements

My strategy:
1. Run baseline (current main code) at 3000 steps and 10000 steps to quantify death timing
2. Apply stuck_threshold=30 (proven improvement from eTn0X)
3. Explore additional longevity ideas: proactive heart withdrawal timing, HP-aware late-game mode

2026-05-04T08:01: starting to run baseline

## Baseline Results (5-seed, 3000 steps, 8-agent self-play)

| Seed | Total Reward | Per Agent |
|------|-------------|-----------|
| 42 | 1126.10 | 140.76 |
| 123 | 1095.66 | 136.96 |
| 7 | 1227.77 | 153.47 |
| 44 | 1266.05 | 158.26 |
| 99 | 1087.16 | 135.89 |
| **Avg** | **1160.55** | **145.07** |

Key observations:
- No deaths at 3000 steps in self-play (hp.amount=800 = full HP for all 8 agents)
- HP stays at ~100 throughout — natural hub healing compensates for drain
- junction.aligned_by_agent = 53 (seed 42)
- heart.gained = 65, all in first ~1000 steps
- In self-play, agents DON'T die because there's no enemy damage

2026-05-04T08:30: starting new experiment loop

## Experiment 1: Enable aligner HP retreat + productive defend

**Hypothesis**: Enabling HP retreat for aligners (currently disabled — `_read_hp()` returns None)
will save agents from death in online matches without regressing offline. Using 25% enter / 70% exit
thresholds ensures the retreat only triggers in genuine danger.

**Changes**:
1. Override `_read_hp()` in LLMAlignerPolicyImpl to return actual HP (was returning None)
2. HP retreat at 25% enter / 70% exit with base HP cap at 100
3. Productive defend mode: explore for junctions instead of nooping when hub depleted

**Results**: 5-seed validation shows ZERO regression — all seeds produce identical rewards.
The HP retreat triggers once in seed 123 (agent 5 hits 24 HP, retreats, recovers immediately)
but the alignment time lost is negligible.

**Online benefit**: In adversarial matches where agents take sustained damage and can't heal,
the 25% threshold will trigger retreat to hub/friendly territory, keeping agents alive longer.
The productive defend mode ensures agents discover new junction targets when hub hearts deplete
(online hub depletes much faster due to competition).
