# Experiment Log: claude/amazing-meitner-uTokl

## Issue: #50 — Close the 21% gap to #1: per-agent alignment efficiency tuning

2026-04-26T00:00: autoresearch starting, my plan is to:
1. Run a 10-seed baseline to establish current performance
2. Test JUNCTION_ALIGN_DISTANCE 20→15 (suggested by wKR1D branch data)
3. Tune heart wait time (try 4 and 8 in addition to current 6)
4. Sweep hub_dist weight more finely (0.1-0.5)
5. Implement aligner heart cooldown on failure (progressive backoff)
6. Implement aligner-aligner coordination (avoid duplicate junction targets)

Target: offline 10-seed avg > 190 (current: 171.73), online score > 36.0

2026-04-26T00:00: starting to read codebase and run baseline

2026-04-26T17:25: baseline result confirmed:
10-seed avg (42-51) = 171.73: 246.13/91.11/134.85/169.41/149.15/139.11/216.19/193.78/203.37/174.16
This matches the previous xh27M branch result exactly, confirming our branch starts from the same code.

---

## Experiment 1: JUNCTION_ALIGN_DISTANCE 20→15

2026-04-26T17:25: starting new experiment loop, in this experiment I want to try reducing JUNCTION_ALIGN_DISTANCE from 20 to 15. My hypothesis is that the game config uses 15 as the actual alignment distance, so our code's use of 20 causes aligners to waste time trying to align junctions that are too far from the network to actually count. The wKR1D branch showed +5.2% reward and +17% junctions at 10k steps with this change.
