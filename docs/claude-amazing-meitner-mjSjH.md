# Experiment Log: claude-amazing-meitner-mjSjH

## Issue: #50 — Close the 21% gap to #1: per-agent alignment efficiency tuning

## 2026-04-27T00:00: autoresearch starting

My plan is to continue the work from the uTokl session on issue #50. That session achieved a 10-seed avg of 197.00 (up from 171.73 baseline) with these kept improvements:
- hub_dist weight 0.3→0.2 (+2.6%)
- max_hearts 3→4 (+0.8%)
- 3A+5M ratio with static aligner IDs 0,3,7 (+14.7%)
- Miner safe wander (defensive, avoids hazard stations)

I've integrated all 4 changes into the current branch. Next experiments to try:
1. Aligner-aligner coordination (enforce target separation more aggressively)
2. Smarter junction prioritization (density bonus, enemy proximity penalty)
3. Cross-role conversion (idle aligner → temp miner)
4. BFS improvements (congestion-aware pathfinding)

## 2026-04-27T00:01: starting to run baseline

Running 10-seed baseline (seeds 42-51) with integrated uTokl improvements at 1000 steps.
