# Experiment Log: claude/amazing-meitner-xh27M

## Issue: #49 — Submit v43 with partner robustness fix

2026-04-25T17:14: autoresearch starting, plan is to:
1. Merge partner robustness fix from Y1TiB branch (dynamic role assignment + adaptive return_load)
2. Validate offline with 8 agents and 4+4 noop split
3. Upload as v43 to beta-cvc
4. Also close #48 (crash-prevention wrappers already on main)

Context: v42:v1 is our best at #105/229 (score 18.74, 34 matches). v42:v2/v3 failed (None scores — likely resubmission issue). The partner robustness fix from #47 branch Y1TiB was NOT yet merged to main despite being referenced as "merged" in #49.

2026-04-25T17:14: starting to run baseline

2026-04-25T17:16: baseline result (pre-merge, main @ cbbc1e9):
- 8 agents, 500 steps, seed 42: total_reward=32.82, avg=4.10/agent
- Role assignment: STATIC — agents 0-4 aligner, 5-7 miner
- Problem: if tournament gives us IDs 0-3 in 4+4 split → ALL aligners, 0 miners

2026-04-25T17:16: merged Y1TiB branch (fast-forward to 761fcb5):
- Dynamic proportional role assignment: A,M,A,M,A,A,M,A pattern
- Adaptive return_load: <3 miners → cargo threshold drops from 40→26

2026-04-25T17:17: post-merge validation:
- 8 agents, 500 steps, seed 42: total_reward=32.72, avg=4.09/agent (no regression)
- Role assignment: PROPORTIONAL — A,M,A,M,A,A,M,A (5A+3M interleaved)
- 4+4 noop test, 500 steps, seed 42: total_reward=27.14, avg=3.39/agent
  - 4 real agents get A,M,A,M (2 aligners + 2 miners) — correct!
- 8 agents, 1000 steps, seed 42: total_reward=131.37, avg=16.42/agent

2026-04-25T17:22: uploaded lessandro-scripted-v43:v1 to beta-cvc
- Bundle: 79 KB, 23 files
- Policy class: MachinaLLMRolesPolicy (scripted miners + scripted aligners)
- Added to qualifying pool

Expected impact: v42's bad-partner matches scored 0-2 (10 of 34 matches). With the fix,
those matches should score 10-15+ since we'll now have miners even with weak partners.
Average score should jump from 18.74 → ~25+, improving rank from #105 → ~#80-90.

## Next steps
- Wait for 5-10 matches to complete on v43
- Check split-specific scores (4+4 and 6+2 splits)
- If v43 shows improvement, move to further offline reward optimization

---

## Experiment 2: Reduce cooldown over-blocking — FAILED, REVERTED

2026-04-25T17:28: hypothesis was that MOVE_COOLDOWN=6 is too aggressive.
Changes: cooldown TTL 6→3, deposit stale min 6→10, clear cooldowns on skill change.

Result: WORSE. 131.37 → 112.46 total reward. max_steps_without_motion 47 → 253.
Cooldowns actually HELP navigation by forcing agents to find alternative paths.
Clearing on skill change was especially bad — stale cooldowns represent real walls.

Learning: cooldowns are GOOD for the BFS pathfinding. Don't reduce them.

---

## Experiment 3: Increase stuck_threshold 20→30 — FAILED, REVERTED

2026-04-25T17:33: hypothesis was that agents abort too early.
Changes: stuck_threshold 20→30 (deposit timeout 40→60, mine timeout 100→150).

Result: WORSE. 131.37 → 96.22 total_reward (-26.7%). Hearts dropped 33→29.
Agents waste more time stuck instead of switching to productive alternatives.

Learning: stuck_threshold=20 is already well-tuned. Don't increase it.

---

## Experiment 4: Reduce aligner_fraction 62.5%→50% — SUCCESS, KEPT

2026-04-25T17:36: key observation from logs: aligners are heartless 59% of the time
(54/91 decision points). With 5 aligners competing for hearts from 3 miners, there's
a severe production bottleneck.

Changes: aligner_fraction for ≥6 agents: (n-3)/n → 0.5. Gives 4A+4M instead of 5A+3M.

Result: IMPROVED. 5-seed validation (seeds 42-46):
- 4A+4M avg: 122.64 (137.78, 91.74, 109.78, 164.04, 109.86)
- 5A+3M avg: 115.63 (131.37, 91.41, 136.45, 108.97, 109.95)
- Improvement: +6.1% on average

Learning: heart production was the bottleneck, not junction coverage. 4 productive
aligners beat 5 idle ones. High seed variance (91-164) driven by map layout.

---

## Experiments 5-7: Navigation improvements — ALL REVERTED

Tested three navigation changes, all neutral on 5-seed average:
- Exp 5: deposit retry with rotated side (avg 121.34 vs 122.64)
- Exp 6: increase HUB_ALIGN_DISTANCE 25→30/40 (avg 122.02/116.95 vs 122.64)
- Exp 7: gear_up approach side diversification (avg 123.34 vs 122.64)

Learning: navigation improvements help some seeds but hurt others. The variance
is dominated by map layout (corridor width, hub position) not agent behavior.
Move failures are 3.2% on good maps vs 12.9% on bad maps.

---

## Experiment 8: Reduce hub_dist junction targeting weight — SUCCESS, KEPT

2026-04-25T18:30: the junction targeting score was `travel + hub_dist * 0.7`.
The hub proximity bias made aligners avoid far-from-hub junctions even when
they were close to the agent. Sweeping the weight:

| Weight | 5-seed avg | Delta |
|--------|-----------|-------|
| 0.0 | 128.80 | +5.0% |
| 0.2 | 128.29 | +4.6% |
| 0.3 | 129.32 | +5.4% |
| 0.5 | 126.44 | +3.1% |
| 0.7 | 122.64 | baseline |

Changed to 0.3. Also tested aligner ratios comprehensively:

| Ratio | 5-seed avg |
|-------|-----------|
| 8A+0M | 51.65 |
| 6A+2M | 110.61 |
| 5A+3M | 115.63 |
| 4A+4M | 122.64 |
| 3A+5M | 121.26 |

Combined improvements: 5A+3M baseline 115.63 → 4A+4M + hub_dist=0.3: 129.32 (+11.8%).

---

## Experiment 9: Junction-based deposits for miners — FAILED, REVERTED

2026-04-25T19:10: Hypothesis: miners deposit at friendly junctions (closer than hub)
to reduce travel time. Junctions have a remote deposit handler.

Result: WORSE. 5-seed avg 127.73 vs 129.32 (-1.2%). Mixed per-seed results.
Root cause: depositing at junctions bypasses the hub's make_heart handler.
Hearts only get made when agents visit the hub directly. Junction deposits
delay heart production, which is the primary bottleneck.

Learning: hub visits are essential for heart production. Can't shortcut them.

---

## Experiment 10: Multi-heart accumulation for aligners — SUCCESS, KEPT

2026-04-25T19:26: Key observation: aligners leave the hub with just 1 heart,
making expensive round trips for each junction alignment. If they accumulate
multiple hearts, they can align 2-3 junctions per trip.

Changes: when near the hub (Manhattan dist ≤ 2), aligners wait to collect
up to 3 hearts before leaving. Uses a 3-tick no_progress timeout to avoid
indefinite waiting if hub is empty.

Result: 5-seed avg 143.08 vs 129.32 (+10.6%)
- Seed 42: 189.77 vs 157.54 (+20.4%) — 43 junctions aligned vs 33
- Seed 43: 98.95 vs 84.93 (+16.5%)
- Seed 44: 120.77 vs 118.04 (+2.3%)
- Seed 45: 157.75 vs 159.16 (-0.9%)
- Seed 46: 148.18 vs 126.92 (+16.7%)

Also tested heart_target=2: identical results — aligners naturally get 2 hearts
before the timeout. The 3rd heart is rarely available within 3 ticks.

Combined: 5A+3M baseline 115.63 → 143.08 (+23.7%)

Uploaded as lessandro-scripted-v46:v1 to beta-cvc.

---

## 10k step scaling test

2026-04-25T19:03: 10k steps (tournament length), seed 42, pre-multi-heart:
- total_reward=3267.50, avg_per_agent=408.44
- junction.aligned=50 out of 53 on map
- heart.gained=54, heart.lost=50
- Move failure rate: 12.3% (9817/80000)
- 4 agent deaths
- Resources: C=1192, O=900, Ge=920, Si=1290

Key finding: 53 junctions on map, not 4-6 as previously assumed.
Offline 10k performance is very high; the gap to online (18.74/agent)
is due to opponents recapturing junctions and weak partner agents.

---

## Experiment 11: Multi-heart wait_time tuning — SUCCESS, KEPT

2026-04-25T19:40: the multi-heart accumulation (experiment 10) used
no_progress_on_target_steps < 3 as the timeout. Hypothesis: 3 ticks
is too short — aligners leave with 1 heart before the hub can make more.

Wait-time sweep (5-seed avg, seeds 42-46):

| wait_time | 5-seed avg | Delta vs wait=3 | Per-seed |
|-----------|-----------|-----------------|----------|
| 3 | 143.08 | baseline | 189.77/98.95/120.77/157.75/148.18 |
| 5 | 153.77 | +7.5% | — |
| 6 | **162.38** | **+13.5%** | 191.12/103.67/152.53/157.17/207.43 |
| 7 | 138.81 | -3.0% | — |
| 8 | 151.87 | +6.1% | — |

Non-monotonic relationship: sweet spot at 6 ticks. With wait=6, aligners
get 2+ hearts reliably before leaving. wait=7+ wastes time when hub is empty.

Combined improvement stack:
1. aligner_fraction 62.5%→50% (4A+4M): +6.1%
2. hub_dist weight 0.7→0.3: +5.4%
3. multi-heart accumulation (wait=3): +10.6%
4. wait_time tuning (3→6): +13.5%

**Total: 5A+3M baseline 115.63 → 162.38 = +40.4%**
