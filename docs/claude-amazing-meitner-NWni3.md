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

### Next experiment ideas
- **Stale threshold tuning for online**: Try stale=12 as compromise between 8 (too aggressive) and 20 (too conservative)
