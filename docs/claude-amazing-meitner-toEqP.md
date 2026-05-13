# Experiment Log: claude-amazing-meitner-toEqP

## Issue #71: Junction control efficiency — 74% vs Softy's 84%

### Goal
Improve junction control fraction from ~74% to 80%+ by optimizing aligner behavior, coordination, and junction acquisition efficiency.

---

## 2026-05-13 05:15: Autoresearch starting

My plan is to improve junction control efficiency by:
1. Investigating SharedMap coordination (currently NOT passed to aligners in MachinaRolesPolicy)
2. Optimizing heart pipeline (more hearts per trip = fewer hub returns)
3. Improving junction prioritization (cascade order, TSP-like routing)
4. Testing more aligners (3A+5M or 4A+4M vs current 2A+6M)

## 2026-05-13 05:17: Starting baseline run

Running 3-episode scrimmage with machina_roles, 8 agents, 3000 steps, seeds via episodes.

### Baseline Results (machina_roles, 2A+6M, 3000 steps)
- Episode rewards: 0.557, 0.611, 0.575
- Average: 0.581
- Junction held (cogs): 2809 avg
- Junction gained: 2.94 avg
- Hearts withdrawn: 5.0 avg
- Clips junction held: 183,120 avg (clips dominate)

Key observation: With only 2 aligners and no SharedMap coordination, junction control is extremely low. Aligners likely duplicate effort and waste time.

### Corrected Baseline (machina_llm_roles, 4A+4M scripted, 3000 steps)
- Episode rewards: 3.454, 1.234, 3.381
- Average: 2.690
- Junction held (cogs): 23,897 avg
- Junction gained: 53.7 avg
- Hearts withdrawn: 347 avg
- Clips junction held: 183,120 avg

---

## Experiment 1: Increase heart accumulation to 5

2026-05-13 05:28: NO EFFECT. Hub can't produce hearts fast enough — aligners only get 1 heart per trip regardless of threshold. The bottleneck is heart PRODUCTION, not collection capacity.

## Experiment 2: Network-expansion-aware junction priority

2026-05-13 05:40: Added cascade_count bonus to junction scoring. Marginal +1% improvement (within noise). Reverted — not worth the O(n²) overhead.

## Experiment 3: 5 aligners (5A+3M) instead of 4A+4M

2026-05-13 05:48: Increased aligner fraction from 0.5 to 0.625.

### Results
| Metric | Baseline (4A+4M) | 5A+3M | Change |
|--------|------------------|-------|--------|
| Avg reward | 2.690 | 2.892 | +7.5% |
| Junction held | 23,897 | 25,916 | +8.4% |
| Junction gained | 53.7 | 62.0 | +15.5% |
| Episode 0 | 3.454 | 3.810 | +10.3% |
| Episode 1 | 1.234 | 2.280 | +84.7% |
| Episode 2 | 3.381 | 2.585 | -23.5% |

Heart production dropped significantly (347→22 withdrawn) due to fewer miners, but junction gains still improved. The extra aligner more than compensated. Variance is high — episode 2 regressed.

## Experiments 4-7: Various parameter tuning (discarded)

- **5A-tuned** (stuck_threshold=15 + defend-when-starved): -24.6%. Lower timeout and defending waste time.
- **Heart queue max(4)**: +3.6% median improvement with 5 aligners. Prevents 2/5 aligners from being permanently heart-starved.
- **Contamination avoidance**: No effect in self-play (expected — helps online). Kept as defensive measure.
- **JUNCTION_ALIGN_DISTANCE=30**: -20.8%. Too far, aligners waste time traveling.
- **hub_dist=0.5**: -10.1%. Stronger hub bias limits junction selection.
- **hub_dist=0.1**: -9.9%. Weaker hub bias causes poor route planning.
- **MOVE_COOLDOWN=4**: -13.0%. Too aggressive retry causes collision loops.
- **Heart patience=6**: -13.0%. Aligners waste time at empty hub.
- **HUB_ALIGN_DISTANCE=35**: Worse than 30. Too far.

## Experiment 8: HUB_ALIGN_DISTANCE=30 (BEST)

2026-05-13 07:55: Increased HUB_ALIGN_DISTANCE from 25 to 30. This expands the zone around the hub where junctions are directly alignable WITHOUT needing cascade from other junctions. Critical for early game when the alignment network is small.

### Results (5-episode average)
| Metric | Baseline (4A+4M) | Best config | Change |
|--------|------------------|-------------|--------|
| Avg reward | 3.165 | 3.265 | +3.2% |
| Median | 3.381 | 3.898 | +15.3% |
| Junction held | ~23,897 | ~29,655 | +24.1% |
| Junction gained | ~53.7 | ~62.6 | +16.6% |

### Final configuration
- aligner_fraction=0.6 (5A+3M for 8 agents, 2A+2M for 4 agents)
- heart_queue=max(4, available) instead of max(3, available)
- HUB_ALIGN_DISTANCE=30 (was 25)
- JUNCTION_ALIGN_DISTANCE=25 (reverted from 30 experiment)
- Aligner contamination avoidance in BFS (defensive for online)

Key learnings:
1. More aligners (5 vs 4) directly improves junction control throughput
2. HUB_ALIGN_DISTANCE=30 > 25 because more junctions are alignable without cascade
3. JUNCTION_ALIGN_DISTANCE=25 is still optimal (30 causes travel waste)
4. Hub_dist=0.2 scoring weight is the sweet spot
5. Heart production is NOT the bottleneck — alignment cycle time is

## Session 2: 2026-05-13 08:30

### Experiments 9-16: Parameter tuning (all discarded)

| Experiment | Avg Reward | Change | Why |
|-----------|-----------|--------|-----|
| Enemy junction bonus=-5 | 3.000 | -8.1% | Travel overhead to distant enemy junctions |
| Enemy junction bonus=-2 | 3.228 | -1.1% | Still not worth the travel |
| 6A+2M (fraction=0.75) | 1.809 | -44.6% | Too few miners kills heart production |
| JUNCTION_ALIGN_DISTANCE=28 | 2.408 | -26.3% | Worse than 30, travel waste |
| Heart accumulation=2 | 3.265 | 0% | Identical — aligners rarely get >1 heart |
| L2 distance fix (15/25) | 2.946 | -9.8% | Strict matching loses look-ahead benefit |
| return_load=25 | 2.345 | -28.2% | More trips = too much miner travel overhead |
| get_heart timeout=60 | 2.550 | -21.9% | Too short, hearts need time to craft |

### Key discovery: game uses L2 distance (dr²+dc² ≤ r²), not Manhattan

Game config: JUNCTION_ALIGN_DISTANCE=15 (L2), HUB_ALIGN_DISTANCE=25 (L2). Our Manhattan 25/30 work as look-ahead heuristics — targeting junctions that will become alignable as the network expands. Strict L2 matching hurts because it loses this look-ahead.

### Experiment 17: Explore instead of defend (BEST — commit 273bbbb)

After get_heart timeout (hub empty), switch to explore instead of defend. Defending wastes time idling on a friendly junction. Exploring discovers new junctions and map cells.

| Metric | Previous best | Explore-not-defend | Change |
|--------|-------------|-------------------|--------|
| Avg reward (5-ep) | 3.265 | 3.417 | +4.7% |
| Avg reward (10-ep) | — | 3.283 | +0.5% |
| Junction held | 29,655 | 31,174 | +5.1% |
| Junction gained | 62.6 | 65.6 | +4.8% |

### Seed 43 diagnosis

Seed 43 consistently scores ~1.7 due to MINER gear contamination (walking through hazard stations), not aligner issues. Miners get stuck in gear_up loops for hundreds of steps. The BFS hazard avoidance works but can't prevent first-contact contamination through unknown cells (optimistic BFS).

### Current best configuration (273bbbb)
- aligner_fraction=0.6 (5A+3M for 8 agents)
- heart_queue=max(4, available)
- HUB_ALIGN_DISTANCE=30, JUNCTION_ALIGN_DISTANCE=25 (Manhattan, acts as look-ahead)
- Contamination avoidance in BFS
- Explore instead of defend after heart timeout
- heart accumulation threshold=4 (consistent across plan/finish)

## Experiment 18: Aligner spread bonus + miner junction deposit (ec2b9ca)

2026-05-13 15:00: Two combined improvements:

1. **Aligner spread bonus (weight=0.05)**: Added spread_bonus to `_cascade_priority_target` scoring. When other aligners are targeting nearby junctions, add a small penalty to encourage spread. Weight 0.05 is gentle enough to not override travel/hub_dist priorities but prevents multiple aligners clustering on the same junction group.

2. **Miner junction deposit**: Miners now deposit at the nearest friendly junction when it's >5 cells closer than the hub. Junctions relay deposits to the hub via `queryDeposit`, so resources still reach the crafting pipeline. Reduces miner travel time when far from hub.

### Results (10-episode average)
| Metric | Baseline (273bbbb) | Combined (ec2b9ca) | Change |
|--------|-------------------|---------------------|--------|
| Avg reward | 3.283 | 3.469 | +5.7% |
| Min | 2.125 | 1.916 | — |
| Max | 5.765 | 5.933 | — |

Episodes: 2.856, 1.916, 5.590, 2.615, 5.933, 2.846, 3.688, 4.043, 2.036, 3.171

### Updated best configuration (ec2b9ca)
- aligner_fraction=0.6 (5A+3M for 8 agents)
- heart_queue=max(4, available)
- HUB_ALIGN_DISTANCE=30, JUNCTION_ALIGN_DISTANCE=25 (Manhattan, acts as look-ahead)
- Contamination avoidance in BFS
- Explore instead of defend after heart timeout
- heart accumulation threshold=4
- **NEW**: Aligner spread bonus weight=0.05 in cascade priority scoring
- **NEW**: Miner junction deposit when junction >5 cells closer than hub

## Experiment 19: Nearby enemy junction recapture priority (4953971)

2026-05-13 15:35: Added enemy_bonus=-3 to junction priority scoring, gated by travel distance ≤ 15. Recapturing enemy junctions is a +2 swing for the same heart cost. Previous experiments without distance gating failed (bonus=-5: -8.1%, bonus=-2: -1.1%) because aligners traveled too far.

### Results (10-episode average)
| Metric | Previous best (ec2b9ca) | Enemy recapture (4953971) | Change |
|--------|------------------------|---------------------------|--------|
| Avg reward | 3.469 | **3.619** | **+4.3%** |
| Max episode | 5.933 | **7.769** | +30.9% |

Also tested:
- bonus=-5 gated: 3.574 (5-ep) — too aggressive
- return_load=30: 2.633 (5-ep, -24.1%) — too many trips

### Updated best configuration (4953971)
- aligner_fraction=0.6 (5A+3M for 8 agents)
- heart_queue=max(4, available)
- HUB_ALIGN_DISTANCE=30, JUNCTION_ALIGN_DISTANCE=25 (Manhattan, acts as look-ahead)
- Contamination avoidance in BFS
- Explore instead of defend after heart timeout
- heart accumulation threshold=4
- Aligner spread bonus weight=0.05
- Miner junction deposit when junction >5 cells closer than hub
- **NEW**: Enemy junction recapture bonus=-3 when travel ≤ 15
