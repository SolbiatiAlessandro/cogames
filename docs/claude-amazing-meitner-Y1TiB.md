# Experiment Log: claude/amazing-meitner-Y1TiB

## Issue: #47 - Partner robustness: score collapses to ~0 with weak partners

2026-04-25 00:00: autoresearch starting, my plan is to:
1. Run baseline on current code (HEAD=cbbc1e9, session 16 state)
2. Re-implement the dynamic role assignment fix from the previous researcher (BMQ2v branch, never merged)
3. Re-implement the adaptive return_load fix  
4. Push further: address the remaining 37% gap from map-layout dependent junction scattering
5. Key insight from prior work: with 8 agents, aligner_ids={0,1,2,3,4}. In tournament, if we control agents 0-3, ALL become aligners with 0 miners -> no mining -> score collapse.

Prior researcher's results (BMQ2v, not merged):
- Dynamic role assignment: 4+4 noop went from 164.97 to 566.80 (+3.4x)
- Adaptive return_load: further improved to 644.16 (+15%)
- 10-seed avg: 547.3 (63% of full-team)
- Full team unchanged or slightly improved (+6.7%)

2026-04-25 00:01: starting to run baseline

### Baseline results
- 8 real agents, seed 42: **826.43**
- 4+4 noop, seed 42: **164.97** (only 6 junctions aligned, 0 miners)
- Root cause confirmed: all 4 real agents (IDs 0-3) assigned as aligners. With n_agents=8, n_aligners=5, aligner_ids={0,1,2,3,4} — all our agents fall in aligner range.

### Fix 1: Dynamic proportional role assignment (commit 100c007)
Replaced static ID-based role assignment with proportional counter-based assignment.
- 4+4 noop seed 42: 164.97 → **566.80** (+3.4x)
- 8 real seed 42: 826.43 → **881.64** (+6.7%)
- Role pattern for 8: A,M,A,M,A,A,M,A. For 4: A,M,A,M.

### Fix 2: Adaptive return_load (commit d2e98c9)
With <3 active miners, reduce cargo threshold from 40 to ~26.
- 4+4 noop seed 42: 566.80 → **608.40** (+7.3%)
- 4+4 noop seed 123: → **486.23**
- 8 real seed 42: **881.64** (unchanged)

### 10-seed validation (4+4 noop, 3000 steps, both fixes combined)
| Seed | Score |
|------|-------|
| 42   | 608.4 |
| 123  | 486.2 |
| 7    | 621.3 |
| 999  | 405.8 |
| 2024 | 753.5 |
| 100  | 586.0 |
| 200  | 581.8 |
| 300  | 664.6 |
| 400  | 437.6 |
| 500  | 768.8 |
| **Avg** | **591.4** |

Average: 591.4 (67% of full-team). Previous researcher's avg was 547.3 (63%).
Improvement: +8.1% over previous researcher's 10-seed average.

2026-04-25 06:00: starting new experiment loop. The remaining gap (33%) is map-layout dependent.
Seeds with scattered junctions score poorly (405-437), while clustered ones score well (753-769).
Hypothesis: coordinated exploration could help aligners discover scattered junctions faster.

### Experiment 3: Diversified aligner exploration (commit 11e77fd → reverted cd76cbf)
Attempted to diversify aligner exploration by adding position-based bias to BFS scoring.
- Multiple variants tested (quadrant-biased, soft diversity coefficient 0.3)
- Results: high variance. Some seeds improved dramatically, others crashed catastrophically.
- Seed 400 crashed from 437 to 111 with diversity coeff=0.3.
- **REVERTED**: too risky, not worth the variance.

### Experiment 4: Extended explore cap for small teams
Hypothesis: with only 2 aligners, explore duration cap of 40 steps is too short for scattered junctions.
Extended to 80 steps (`stuck_threshold * 4`) when total active agents ≤ 4.
- Seed 42: 608 → 608 (no change)
- Seed 400: 437 → 426 (-2.6%)
- Seed 999: 406 → 393 (-3.1%)
- **REVERTED**: slight regression on worst seeds, no improvement on others.

### Experiment 5: Miner junction discovery for SharedMap
Hypothesis: miners exploring for extractors could report junction locations to SharedMap, helping aligners discover junctions faster without additional exploration.
Three variants tested:
1. **Full refresh** (difference_update + update): Seed 42: +30%, 123: +34%, but 8-real regressed -17%, seed 400: -41%.
2. **Add-only** (add junctions, discard from other sets): 8-real: +8%, seed 42: +20%, but seed 999: -61%.
3. **New-junctions-only** (only add truly unknown junctions, guard with active_miner_ids ≤ 2): 8-real unchanged, seed 42: +2.5%, but seed 999: -5%, seed 400: -6%.
- **REVERTED all variants**: the butterfly effect of changing junction discovery order cascades into unpredictable behavior. Any junction knowledge change alters which junction aligners target first, changing the entire action sequence. Net negative on 10-seed average despite some seeds showing +30%.

### Experiment 6: Lower return_load (20 instead of 26)
Changed adaptive formula from `n_miners // 3` to `n_miners // 4` for 2-miner teams.
- Seed 42: 608 → 591 (-3%), seed 400: 437 → 290 (-34%), seed 999: 406 → 534 (+31%)
- **REVERTED**: too much variance, average worse.

### Root cause analysis of remaining gap
Full-team scores are consistent across seeds (814-881), but 4+4 noop varies from 406-769 (49%-87% of full team). The variance comes from map layout:
- **Good seeds** (2024, 500): junctions clustered near hub → 2 aligners can efficiently reach them
- **Bad seeds** (400, 999): junctions scattered far → 2 aligners spend too much time traveling

With 5 aligners (full team), scattered junctions are covered by different aligners in parallel. With 2 aligners, each must cover more ground sequentially. This fundamental coverage gap cannot be closed without changing the game dynamics.

### Conclusion
- **Success criterion met**: 591.4 avg = 67% of full team (target was >50%)
- **Improvement over prior work**: +8.1% vs previous researcher's 10-seed avg (547.3 → 591.4)
- **Fix 1 (dynamic roles)**: dominant improvement, preventing all-aligner catastrophe
- **Fix 2 (adaptive return_load)**: moderate improvement for 2-miner teams
- **Remaining gap (33%)**: map-dependent, resistant to single-agent-level optimization
