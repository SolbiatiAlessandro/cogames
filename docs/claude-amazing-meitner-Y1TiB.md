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
