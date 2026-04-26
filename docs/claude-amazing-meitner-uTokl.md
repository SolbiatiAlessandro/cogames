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

2026-04-26T17:35: RESULT JUNCTION_ALIGN_DISTANCE=15 — WORSE, REVERTED
10-seed avg = 168.64 vs baseline 171.73 (-1.8%)
Seeds: 245.85/61.42/136.64/157.80/128.77/132.52/219.00/200.10/229.02/175.25
Seed 43 dropped dramatically (91→61). The tighter distance prevents aligners from reaching
some junctions that were borderline-accessible. At 1000 steps the broader exploration radius
helps more than it wastes. The wKR1D 10k result may not transfer to 1000 steps.

Learning: JUNCTION_ALIGN_DISTANCE=20 is better than 15 at 1000 steps. The broader range
allows aligners to reach more junctions. Don't reduce it.

---

## Experiment 2: Heart wait time tuning (wait=4 and wait=8)

2026-04-26T17:36: starting new experiment. Currently aligners wait at hub until they have 3 hearts OR until 6 steps without progress (no_progress_on_target_steps < 6). The xh27M branch tested wait=3 and wait=6, finding 6 optimal. I'll test wait=4 and wait=8 to find if there's a better sweet spot.

2026-04-26T17:45: RESULT wait=4 — MUCH WORSE, REVERTED
10-seed avg = 150.94 vs baseline 171.73 (-12.1%)
Seeds: 226.53/98.30/82.84/172.42/98.94/101.65/203.67/183.74/164.96/176.38
Aligners leave hub too early with only 1 heart, wasting travel time.

2026-04-26T17:50: RESULT wait=8 ��� WORSE, REVERTED
10-seed avg = 163.64 vs baseline 171.73 (-4.7%)
Seeds: 217.94/67.78/114.30/199.22/144.25/125.64/233.86/186.33/167.11/179.99
Longer wait blocks the hub, preventing other aligners from getting hearts.

Learning: wait=6 is the optimal value. Don't change it.

---

## Experiment 3: Hub_dist weight sweep (cascade priority)

2026-04-26T17:51: starting new experiment. The _cascade_priority_target function scores junctions as: travel_distance + hub_dist * 0.3. The xh27M branch tested 0.7→0.3 and found improvement. Let me try finer sweep: 0.1, 0.2, 0.4, 0.5 to find the optimum.

2026-04-26T18:05: RESULT hub_dist weight sweep — 0.2 IS BEST, KEPT
- 0.1: avg=170.04 (-1.0%)
- 0.2: avg=176.26 (+2.6%) ← BEST
- 0.3: avg=171.73 (baseline)
- 0.4: avg=175.12 (+2.0%)
- 0.5: avg=175.19 (+2.0%)

Notable seed improvements with 0.2: seed 44 (134→158, +17%), seed 46 (149→166, +11%).
The lower weight means travel distance dominates — aligners pick nearer junctions first,
reducing wasted navigation time. Hub proximity still helps break ties.

Learning: 0.2 is the sweet spot. Going lower (0.1) loses the hub-proximity signal; going
higher (0.4-0.5) makes aligners skip nearby junctions for distant hub-close ones.

---

## Experiment 4: Aligner heart cooldown on failure (progressive backoff)

2026-04-26T18:06: starting new experiment. When get_heart fails (times out), the aligner currently gets a timeout counter but immediately retries. The wKR1D branch had a `get_heart_cooldown_steps` feature that backs off progressively. My hypothesis is that after a timeout at the hub (likely empty), the aligner should do something productive (explore, defend) before retrying, rather than camping at an empty hub.
