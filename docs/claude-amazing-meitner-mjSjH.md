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

### Baseline result: 10-seed avg = 200.09

Seeds: 237.38/200.36/212.28/222.83/193.54/165.26/225.55/238.06/137.63/167.99
- Matches uTokl (197.00) closely — 6 of 10 seeds identical
- Secondary target (>190) already achieved
- Worst seed: 50 (137.63), best: 49 (238.06)

## 2026-04-27T01:00: starting new experiment loop

In this experiment I want to try improving aligner navigation efficiency. Hypothesis: aligners spend too many steps traveling. If we can improve junction selection or reduce navigation overhead, we can align more junctions per episode.

Looking at the data: seed 50 and 47 are weakest (137.63, 165.26). These are likely seeds with difficult map layouts where junctions are far from hub. Targeting these outliers could have the biggest impact on average.
