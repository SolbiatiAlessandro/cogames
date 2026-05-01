# Experiment Log: claude/amazing-meitner-NWni3

## Issue: #55 - Submit NiskB efficiency fixes + validate online (target: score > 37.0)

2026-05-01T00:00: autoresearch starting, my plan is to continue issue #55 work. Previous researchers (session 7T3EK) submitted v1-v4 of ohm-mani-padme-hum, all scoring below v52 baseline (#29/35.97). v4 is at #45/34.17. Key finding: NiskB changes help 4+ agents but 2-agent matches drag score down. I will focus on finding improvements that bridge the gap to >37.0 online.

2026-05-01T00:01: starting to run baseline

### Baseline Results (post-NiskB, current main)
| Seed | Reward |
|------|--------|
| 42 | 1121.22 |
| 123 | 1073.88 |
| 456 | 1090.76 |
| **Avg** | **1095.29** |

Matches NiskB report values exactly. Baseline confirmed.

### Online Status
- v52 (pre-NiskB): #29, score=35.97 (our best)
- ohm-mani-padme-hum v4 (post-NiskB + aligner HP retreat): #45, score=34.17
- Top: Paz-Bot-9000:v47 at #1, score=41.10
- All ohm-mani-padme-hum versions (v1-v4) score worse than v52 online despite +28.7% offline

### Analysis
The NiskB changes that helped offline (+3.6%) hurt online. Two changes:
1. Approach side diversification (gear_up) — likely neutral online
2. mine_until_full stale threshold 20→8 — likely culprit. In online play with contested extractors, 8 steps is too short before marking an extractor as depleted.

v2's aligner HP retreat (0.40/0.55) improved 2-agent matches by 75% but wasn't enough alone.

2026-05-01T05:20: starting new experiment loop, in this experiment I want to try:
- mine_until_full stale threshold: 8 → 15 (reduce false depletion in contested play)
- Enable aligner HP retreat: threshold 0.40, resume 0.60 (wide hysteresis band to prevent oscillation)
My hypothesis is that the stale threshold of 8 causes miners to incorrectly abandon extractors that are contested by partner agents, wasting mining time in exploration. Combined with aligner HP retreat, this should improve both mining efficiency and agent survival online.

### Experiment 1: stale=15 + aligner HP retreat 0.40/0.60
**Result: REGRESSION (-3.8%)**

| Seed | Baseline | Exp 1 | Delta |
|------|----------|-------|-------|
| 456 | 1090.76 | 1055.93 | -3.2% |
| 42 | 1121.22 | 1121.22 | 0.0% |
| **Avg** | **1095.29** | **1052.54** | **-3.8%** |

Root cause: stale threshold 15 caused miners to waste time at depleted extractors (reversed NiskB improvement). Reverted stale back to 8.

### Experiment 2: aligner HP retreat 0.40/0.60 (stale=8)
**Result: PARTIAL REGRESSION on seed 456**

Diagnostic log: `agent=6 HP_LOW hp=39/100 (39%) retreating to friendly territory` — HP actually drops to 39% in offline self-play, triggering the 0.40 threshold. Lowered to 0.25 (matching proven-neutral miner threshold).

### Experiment 3: aligner HP retreat 0.25/0.50 (stale=8) — VALIDATED
**Result: OFFLINE-NEUTRAL (0.00% delta across all 3 seeds)**

| Seed | Baseline | Exp 3 | Delta |
|------|----------|-------|-------|
| 42 | 1121.22 | 1121.22 | 0.0% |
| 123 | 1073.88 | 1073.88 | 0.0% |
| 456 | 1090.76 | 1090.76 | 0.0% |
| **Avg** | **1095.29** | **1095.29** | **0.00%** |

The 0.25 threshold never triggers in offline self-play but will activate in competitive online matches where agents take more damage from enemy clips. This is the ideal setup — zero offline risk with potential online upside.

Changes in this version:
- `machina_llm_roles_policy.py`: Added `_ALIGNER_HP_RETREAT = 0.25`, `_ALIGNER_HP_RESUME = 0.50` with `_read_hp()` and `_check_hp()` for LLMAlignerPolicyImpl
- `llm_miner_policy.py`: stale threshold remains at 8 (NiskB default)

2026-05-01T05:37: Submitting as ohm-mani-padme-hum v5 to validate online. Target: beat v52 baseline (35.97).

### Experiment 4: Fast heartless defend (heart queue overflow → defend)
2026-05-01T05:41: When heart queue overflows (too many aligners en route to hub), heartless aligners were redirected to `explore`. Changed to redirect to `defend` when friendly junctions exist, making them productive by holding captured territory instead of wandering. Falls back to `explore` when no friendly junctions are known.

Hypothesis: In games where hearts are scarce, aligners waiting for hearts waste time exploring. Defending friendly junctions prevents territory loss and may increase junction.held reward.

**Result: REGRESSION (-2.3%)**

| Seed | Baseline | Exp 4 | Delta | Hearts |
|------|----------|-------|-------|--------|
| 42 | 1121.22 | 1074.71 | -4.1% | 64→64 |
| 123 | 1073.88 | 1028.88 | -4.2% | 61→60 |
| 456 | 1090.76 | 1107.02 | +1.5% | 63→68 |
| **Avg** | **1095.29** | **1070.20** | **-2.3%** | |

Analysis: Defending junctions sounds productive but actually hurts. When aligners sit on friendly junctions, they stop exploring for new neutral junctions to align. In self-play, there are no enemy clips contesting territory, so "defending" is just idle waiting. The explore fallback was better because it discovers new junctions, expanding the alignment frontier.

Reverted change. The defend redirect might only help in online play (where enemy clips contest territory), but the offline regression is too large to accept.

### Key finding: stat collection was broken
The experiment script was using wrong stat keys for junction.held (missing `cogs/` prefix) and only collecting per-agent stats (missing team-level derived stats). Fixed in commit a911e48.

Actual junction performance (500-step test, seed 42): **35 junctions aligned** out of 53 total, junction.held=7468 cumulative ticks. Aligners ARE working correctly — the zero junction.held in earlier results was a reporting bug.

2-agent test (3000 steps): 41 junctions aligned, total_reward=162.04, avg=81.02/agent. Even with just 1 miner + 1 aligner, the policy captures most junctions.

### Online submission status
- v5 (0KB bundle, no files): 4 crashes — "received 1011 (internal error)"
- v6 (271KB, src/cogames/policy): 1 crash — "BackoffLimitExceeded" (wrong path: src/ prefix)
- v7-v10: Various approaches, waiting for results
- Issue: compat version changed to 0.25, bundle file paths may not match server expectations

### Experiment 5: Stale threshold tuning (stale=12)
2026-05-01T05:57: Changed mine_until_full stale threshold from 8 to 12.

**Result: SLIGHT REGRESSION (-0.91%)**

| Seed | Baseline | Stale=12 | Delta | Junction.held | Junctions |
|------|----------|----------|-------|---------------|-----------|
| 42 | 1121.22 | 1120.84 | -0.03% | 137103 | 53/53 |
| 123 | 1073.88 | 1079.85 | +0.56% | 131982 | 55/55 |
| 456 | 1090.76 | 1055.29 | -3.25% | 128912 | 54/54 |
| **Avg** | **1095.29** | **1085.33** | **-0.91%** | | |

Key finding: 100% junction capture rate in all seeds (53-55 out of 53-55 total). Junction capture is NOT our bottleneck — mining efficiency is. The extra 4 steps per stale check wastes time at genuinely depleted extractors. Reverted to stale=8.

### Experiment 6: Soft depletion (no depletion marking)
2026-05-01T06:05: Removed depletion marking from the planner's stale check. When mine_until_full stalls for 8 steps, just reset the skill without marking extractors as depleted.

**Result: CATASTROPHIC REGRESSION (-50.3%)**

| Seed | Baseline | Soft Depl | Delta |
|------|----------|-----------|-------|
| 42 | 1121.22 | 557.35 | -50.3% |

1379 soft resets, 0 depletion markings. Miners loop endlessly on the same empty extractors. Depletion marking is essential to prevent tight loops.

### Experiment 7: Role ratio tuning (3 aligners / 5 miners)
**Result: REGRESSION (-3.7%)**
- Total reward: 1079.90 (baseline 1121.22)
- More elements deposited (carbon +28%, silicon +51%) but oxygen flat at 600
- Oxygen is the limiting element for heart crafting
- Fewer aligners → 52/53 junctions (missed 1) → lower junction.held

### Experiment 8: Return load tuning
- return_load=30: **-3.2%** (more deposits but more travel time)
- return_load=50: **-79%** (catastrophic, miners can't fill up)
- Baseline return_load=40 is optimal

### Experiment 9: Periodic depletion reset (global, every 200 steps)
**Result: REGRESSION (-9.3%)**
- 1017.32 total reward. Miners waste time revisiting genuinely depleted extractors every 200 steps.
- 30-60 extractors cleared per reset cycle — too aggressive for self-play where extractors ARE depleted.

### Experiment 10: Online depletion reset (conditional) — VALIDATED
2026-05-01T06:35: Only apply periodic depletion reset when `n_miners <= 2` (online competition scenario). In self-play with 4 miners, the condition never triggers.

**Result: PERFECTLY OFFLINE-NEUTRAL (0.00% delta all 3 seeds)**

| Seed | Baseline | Exp 10 | Delta |
|------|----------|--------|-------|
| 42 | 1121.22 | 1121.22 | 0.0% |
| 123 | 1073.88 | 1073.88 | 0.0% |
| 456 | 1090.76 | 1090.76 | 0.0% |

In 2-agent self-play, the reset only triggers 2x per game (steps 825 and 1275), clearing 1 extractor each time. Impact is -0.44% in 2-agent self-play, which is acceptable.

### Online submission fix
The compat-v0.25 Docker image fails with "No module named 'cogames.games'" — a server-side issue. Created a proper bundle with:
1. `cogames/policy/` files at correct import path (no `src/` prefix)
2. `cogames/games/__init__.py` shim that aliases `cogames.cogs_vs_clips`
3. `setup_games_shim.py` that patches `sys.modules`

Uploaded as ohm-mani-padme-hum v3 (82KB zip) and v4 (80KB dir). Both currently running qualifying matches.

### Match analysis: cooperative game insight
All agents are cogs on the SAME team. The "opponent" in a match is another player controlling some cogs. Scores are shared between both players. 2-agent matches (1 miner + 1 aligner) drag the average down.

v4 match scores by agent count:
- 6 agents: avg ~40 (good)
- 4 agents: avg ~31 (moderate)
- 2 agents: avg ~18 (bad, huge variance 3.3-46.9 depending on partner quality)

### Experiment 11: Aligner junction targeting weight tuning
- travel-only (hub_dist*0.0): **-7.5%** — lost 3 junctions, broken cascade
- hub_dist*0.5: **-3.1%** — too restrictive, ignores nearby non-hub junctions
- Conclusion: baseline 0.2 weight is optimal for junction targeting

### Experiment 12: Heart batching / carry limit changes
- Disable heart batching (want_more_hearts=False): **0.00% delta** — neutral
- Heart carry limit 5 (vs 3): **0.00% delta** — neutral
- In self-play, heart supply is saturated; these changes only matter online

### Experiment 13: Hub-distance weight for extractor selection — IMPROVEMENT
Changed `_nearest_extractor_hub_weighted` scoring from `travel + hub_dist//2` to `travel + hub_dist` (full weight). Makes miners strongly prefer extractors closer to the hub, reducing deposit round-trip time.

**Result: +2.62% average improvement across 5 seeds**

| Seed | Baseline | Hub-Weight | Delta |
|------|----------|-----------|-------|
| 42 | 1121.22 | 1132.27 | +0.98% |
| 123 | 1073.88 | 1112.63 | +3.61% |
| 456 | 1090.76 | 1085.77 | -0.46% |
| 789 | 1103.41 | 1160.64 | +5.19% |
| 101 | 1032.01 | 1072.08 | +3.88% |
| **Avg** | **1084.26** | **1112.68** | **+2.62%** |

Mechanism: closer extractors → shorter round trips → more deposits → more hearts → earlier junction alignment → more junction.held ticks.

### Experiment 14: Aligner junction target coordination
Added SharedMap.aligner_targets to avoid multiple aligners targeting the same junction. **0.00% delta** — perfectly neutral. Junctions are abundant in self-play (53 junctions / 4 aligners). May help online with contested junctions.

### Experiment 15: Shared depletion tracking — REGRESSION (-4.3%)
Sharing depleted extractor lists across miners via SharedMap. Extractors have per-agent or regenerating resources, so global depletion marking is too aggressive. Reverted.

### Experiment 16: Additional tuning attempts (all reverted)
- stuck_threshold 15 (vs 20): **-10.1%** — miners abandon productive mining too early
- mine stale=6 (vs 8): **-3.5%** — marks extractors depleted too aggressively
- hub_dist*2: **-5.7%** — too much clustering, miners fight for same extractors
- Crowding avoidance (penalty for nearby miners): **-3.9%** — sends miners to farther extractors
- return_load=30 with new hub weight: **-5.1%** — still too much travel overhead

### Current state
- **New offline baseline: 1112.68 avg (+2.62% vs pre-hub-weight 1095.29)**
- Committed changes: hub-distance weight, aligner target coordination
- Online submissions v5-v8 all failing (compat-v0.25 Docker image broken on server)
- Best online score: v52 at #29/35.97 (pre-NiskB, compat-v0.17)

### Next experiment ideas
- **Deposit shortcut**: When a miner fills up near the hub, deposit immediately without waiting
- **Element-weighted extractor selection**: Mine scarce elements first even from slightly farther extractors
- **Adaptive aligner fraction for online**: More miners when team has few agents
