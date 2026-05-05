# Autoresearch Session: claude-amazing-meitner-C4lUC

**Issue:** #62 — Junction capture rate & exploration coverage
**Branch:** claude/amazing-meitner-C4lUC
**Base:** c7453c7 (v52 baseline, reverted by director session 27)

## Experiment 4: fix-align-dist-beyond-explore

**Commit:** 11a8e48

### Changes
1. `_JUNCTION_ALIGN_DISTANCE` 20→15 (matches game config `JUNCTION_ALIGN_DISTANCE=15`)
2. New `_explore_beyond_aligned` method — when aligner has heart but no alignable junctions, explore outward from aligned network to find new junctions

### Results (5000 steps, 8-agent self-play)

| Seed | Baseline | Experiment | Delta |
|------|----------|-----------|-------|
| 42 | 1875.99 | 1970.32 | **+5.0%** |
| 1 | 2101.24 | 2101.07 | -0.01% |
| 7 | 2140.73 | 2141.44 | +0.03% |
| **Avg** | **2039.32** | **2070.94** | **+1.55%** |

### Key observations
- Seed 42 benefits from fewer wasted alignment attempts at invalid distances (move.failed: 1846→1327, -28%)
- Seeds 1 and 7 show near-identical results (junctions already within range 15)
- Heart utilization slightly improved across all seeds
- **Decision: KEEP** — net positive, no regression on any seed

## Experiment 5c: get-heart-stale-counting

**Commit:** (pending)

### Changes
1. New specific `get_heart` stale handler — counts consecutive stale exits via `get_heart_timeouts`
2. After 5+ consecutive stale get_hearts, override to `defend` (if friendly junctions) or `explore` (otherwise)
3. Reset `get_heart_timeouts` on successful `align_neutral` completion
4. Explore fallback when no friendly junctions to defend

### Results — Self-play (8-agent, 5000 steps)

| Seed | Exp4 baseline | Exp4+5c | Delta |
|------|--------------|---------|-------|
| 42 | 1970.32 | 1970.32 | 0% |
| 1 | 2101.07 | 2141.56 | +1.9% |
| 7 | 2141.44 | 2141.44 | 0% |
| **Avg** | **2070.94** | **2084.44** | **+0.65%** |

### Results — CvC (2 ours + 6 starter, 5000 steps)

| Seed | Baseline | Exp5c | Delta |
|------|----------|-------|-------|
| 42 | 51.60 | 96.50 | **+87%** |
| 1 | ~5.00 | ~5.00 | 0% |
| 7 | ~5.00 | ~5.00 | 0% |

### Key observations
- No regression in self-play (threshold=5 is conservative enough to never fire in heart-abundant scenarios)
- Seed 1 self-play improvement suggests slightly better skill transitions
- CvC seed 42 nearly doubles — aligners stop futile hub cycling and defend existing junctions instead
- CvC seeds 1 and 7 unchanged (heart scarcity so extreme that even defending doesn't help)
- **Decision: KEEP** — net positive self-play, large CvC win on seed 42

## Next experiments queue
- Reduce miner stale events (174 mine_until_full stales = 3480 wasted steps)
- Reduce `status.max_steps_without_motion` (agents stuck for 151 steps)
- Improve CvC seeds 1 & 7 (extremely low reward — investigate root cause)
- Optimize aligner cycle time in late-game self-play
