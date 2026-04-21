# Experiment Report: Issue #44 — Miner Productivity Plateau

Branch: `claude/amazing-meitner-QzSVo`
Issue: https://github.com/SolbiatiAlessandro/cogames/issues/44

## 2026-04-21T05:15: autoresearch starting, my plan is to...

Working on issue #44: "Miner productivity plateau: deposits freeze at ~5k steps due to extractor depletion radius."

Previous researcher (pva5Z branch, not merged) found the root cause is a **congestion deadlock bug** in `move_blocked_cells`:
1. Move to cell X fails (another agent occupies it)
2. X added to `move_blocked_cells`
3. Next step: X is visible, no wall tag → "visually free" → X **immediately cleared** from `move_blocked_cells`
4. BFS routes through X again → fails again
5. **Infinite loop for 3593+ consecutive steps**

Their fix: per-agent move cooldown of 6 steps. Results: +19.1% avg reward across 3 seeds.

My plan:
1. Run baseline (3 seeds, 3000 steps each)
2. Implement the adaptive move cooldown fix (the pva5Z changes were never merged)
3. Test and iterate
4. Focus on reducing miner deaths (previous researcher noted deaths increased 64 vs 13 because miners now move into dangerous areas more)

## 2026-04-21T05:16: starting to run baseline
