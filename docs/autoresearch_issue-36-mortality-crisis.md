# Autoresearch: Issue #36 - Agent Mortality Crisis

Branch: `claude/amazing-meitner-2Frt2`

## 2026-04-14 05:00: autoresearch starting

**Issue**: [#36](https://github.com/SolbiatiAlessandro/cogames/issues/36) - Agent mortality crisis: ALL agents die before step 10,000 in every online match

**Plan**: Implement the highest-impact fixes from the prior V1-V20 analysis on branch `claude/amazing-meitner-JWpsV` (which was never merged). Key changes:

1. **Hub heart filter (V7)** - Prevent miners from stealing hearts at hub (game-level fix in hub.py)
2. **HP retreat (V7)** - Agents retreat to hub when HP drops below 70%
3. **Fast-path skill selection (V1)** - Skip LLM calls for obvious decisions
4. **Periodic hub return** - Force heartless aligners back to hub every 200 steps
5. **Navigation pre-blocking (V8)** - Block extractors/hubs/stations in BFS
6. **Move-blocked false positive correction (V10)** - Clear false blocks when visually confirmed free
7. **Depleted extractor fix (V12)** - Check adjacent cells since extractors are now blocked
8. **Hub-in-free-cells fix (V11)** - Remembered hub goes to blocked_cells not free_cells
9. **return_load 40->20 (V7/#34)** - Miners deposit twice as often

## 2026-04-14 05:20: starting to run baseline

Running baseline 1k steps with seed 42, 3 agents (2 aligners + 1 miner).

## Results

(to be filled in as experiments complete)
