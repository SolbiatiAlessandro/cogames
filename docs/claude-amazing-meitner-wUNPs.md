# Experiment Log: claude/amazing-meitner-wUNPs

## Issue: #40 — Mining throughput gap

Our best online policy (v32) scores 12.66. Top policies score 40+.
Key gap: we deposit ~500 elements per 10k steps vs 14,000 for top policies (28x gap).

---

### 2026-04-19T05:20: autoresearch starting

**Plan**: Focus on mining throughput improvements (issue #40).

Current state:
- Best online: lessandro-scripted-v32 at 12.66, ranked #68/123
- Top policy: Gryffindor:v11 at 40.82
- Previous work on this branch: stuck-cycle fix, HP retreat bugs, deposit timeout improvements
- Previous best offline: 1.65 at 3000 steps (seed 456)

My approach:
1. Run baseline at 3000 steps with current code to establish starting point
2. Profile miner time breakdown — what fraction of steps are mining vs walking vs stuck
3. Try reducing return_load from 40 to 20 (more frequent, shorter trips)
4. Try optimizing miner routes (cycle between hub-closest extractors)
5. Address agent mortality (agents dying by step 3000)

---

### 2026-04-19T05:21: starting to run baseline

### 2026-04-19T05:30: baseline result

| Metric | Value |
|--------|-------|
| Reward (seed 42) | 1.615 |
| Junctions aligned | 28 |
| Junction held | 13,147 |
| Deposits (C/Ge/Si/O) | 180/180/160/161 (total 681) |
| Deaths per agent | 1.75 |
| Move failure rate | 44% |

Key bottleneck: aligners only use 7 of ~24 available hearts. Miners produce enough, but aligners can't find/reach junctions fast enough.

### 2026-04-19T06:00: Exp 1 — Navigation shake for miners (FAILED)

**Hypothesis**: Adding collision recovery ("shake") to miners (who had none) would reduce wasted steps.
**Result**: FAILED. Reward dropped from 1.615 to 0.877-0.905. The shake deflected agents away from targets (extractors/hubs) when they were intentionally bumping into them to interact. Reverted.

### 2026-04-19T06:30: Exp 2 — Junction scouting from miners (NEUTRAL)

**Hypothesis**: Miners walk past junctions without recording them. If miners shared junction discoveries via SharedMap, aligners would find targets faster.
**Result**: Initial "refresh" approach regressed (miners' updates overwrote aligners' observations). Changed to "additive-only" (miners only ADD junctions, never remove). Neutral result: avg 1.596 vs baseline 1.593.

### 2026-04-19T06:45: Exp 3 — Miner HP retreat 0.70 + junction scouting (KEPT)

**Hypothesis**: Miners die at HP 50%, losing all cargo. Raising retreat threshold from 50% to 70% (matching aligners) would reduce deaths and preserve more mining progress.
**Result**: SUCCESS. Avg reward 1.691 (+6.1%). All 3 seeds improved.

| Seed | Baseline | Exp 3 | Change |
|------|----------|-------|--------|
| 42   | 1.615    | 1.790 | +10.8% |
| 123  | 1.520    | 1.561 | +2.7%  |
| 456  | 1.650    | 1.723 | +4.4%  |
| **avg** | **1.595** | **1.691** | **+6.0%** |

Seed 42 detail: junctions 28→36 (+29%), deposits 681→1190 (+75%), deaths 1.75→1.5 (-14%).

Next: try reducing stuck_threshold, or adjusting aligner explore distance.

### 2026-04-19T06:45: Exp 4 — HP retreat threshold sweep at 10k steps

**Hypothesis**: Higher HP retreat thresholds (0.80, 0.85) may further reduce late-game mortality and improve 10k-step performance.

**Results at 10k steps** (seed 42 only):

| Threshold | Reward | Deaths | Junctions | Junction Held |
|-----------|--------|--------|-----------|---------------|
| 0.70 | 2.490 | 4.0 | 36 | 14904 |
| **0.80** | **2.532** | 4.375 | **39** | **15324** |
| 0.85 | 2.490 | 1.375 | 37 | 14903 |

0.80 best at 10k (+1.7% reward). 0.85 too cautious — fewer deaths but no reward gain.

**Confirmed at 3k steps** (3-seed avg):

| Seed | 0.70 | 0.80 | Change |
|------|------|------|--------|
| 42 | 1.790 | 1.832 | +2.3% |
| 123 | 1.561 | 1.543 | -1.2% |
| 456 | 1.723 | 2.242 | +30.1% |
| **avg** | **1.691** | **1.872** | **+10.7%** |

**Decision**: Adopt 0.80 threshold. Cumulative improvement: +17.4% vs original baseline (1.595 → 1.872).
