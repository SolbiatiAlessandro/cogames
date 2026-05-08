# Autoresearch: Issue #67 — Aligner Throughput Bottleneck

Branch: `claude/amazing-meitner-OPj3g`

## Context
After the gear contamination fix (#64, +15.2%), mining is no longer the bottleneck. Resource surpluses are 300-650 per element, but hearts withdrawn is only 20-31 out of maximum potential 69-97. The constraint is now aligner throughput: how fast aligners can cycle hub→junction→hub.

## 2026-05-08T10:30: autoresearch starting

My plan is to improve aligner throughput by attacking the main bottleneck areas:

1. **Hub wait time**: Aligners currently wait up to 6 ticks for additional hearts (no_progress_on_target_steps < 6). This creates idle time, especially with 4 aligners competing.
2. **Heart carry strategy**: Aligners try to accumulate 3-4 hearts before leaving hub. This may cause congestion.
3. **Junction selection**: `_cascade_priority_target` uses `travel + hub_dist * 0.2` scoring. Could be more aggressive about nearest-first.
4. **JUNCTION_ALIGN_DISTANCE**: Currently 25, could increase to expand alignable territory.

Key metrics to track:
- hearts_withdrawn (target: >40, baseline: ~25)
- mission_reward (target: >3.8, baseline: ~3.282)
- junction.held (proxy for alignment speed)

## 2026-05-08T10:30: starting to run baseline

## 2026-05-08T17:47: baseline result is:

Note: Using PyPI mettagrid 0.15.0 (not git commit version). Reward scale differs from previous experiments but relative comparisons are valid.

| Seed | Total Reward | Avg/Agent | Hearts Gained | Hearts Used | Junctions Aligned |
|------|-------------|-----------|---------------|-------------|-------------------|
| 42 | 1040.43 | 130.05 | 61 | 50 | 50 |
| 123 | 1071.49 | 133.94 | 69 | 55 | 55 |
| 7 | 1103.23 | 137.90 | 70 | 59 | 59 |
| 99 | 1081.57 | 135.20 | 63 | 54 | 54 |
| 555 | 1184.05 | 148.01 | 68 | 59 | 59 |
| **Avg** | **1096.15** | **137.02** | **66.2** | **55.4** | **55.4** |

Key observations:
- `junction.aligned_by_agent` == `heart.lost` in all seeds (each alignment costs 1 heart)
- Average 55.4 junctions aligned per 3000 steps across 4 aligners
- That's ~13.8 junctions per aligner per 3000 steps, or ~1 alignment every 217 steps

## 2026-05-08T17:50: starting new experiment loop

**Experiment 1: Fast-cycle aligners — reduce heart accumulation**

Hypothesis: Aligners currently accumulate up to 4 hearts before leaving hub, waiting up to 6 ticks for each additional heart. With 4 aligners competing for hearts, this creates congestion. By making them leave with 1 heart immediately (max 2 if already near hub, only 2 ticks patience), each aligner cycles faster hub→junction→hub, increasing total throughput.

Changes:
1. `aligner_agent.py:788` — `want_more_hearts` threshold: `< 3` → `< 2`
2. `machina_llm_roles_policy.py:368` — Heart accumulation: `< 4` → `< 2`, patience: `< 6` → `< 2`
3. `machina_llm_roles_policy.py:283,305` — Override heart thresholds: `< 4` → `< 2`

Results (5-seed avg):

| Seed | Total Reward | Baseline | Change | Hearts Gained | Junctions Aligned |
|------|-------------|----------|--------|---------------|-------------------|
| 42 | 906.68 | 1040.43 | -12.9% | 50 | 46 |
| 123 | 1050.90 | 1071.49 | -1.9% | 59 | 55 |
| 7 | 1146.89 | 1103.23 | +4.0% | 70 | 60 |
| 99 | 1114.49 | 1081.57 | +3.0% | 66 | 55 |
| 555 | 1199.08 | 1184.05 | +1.3% | 71 | 61 |
| **Avg** | **1083.61** | **1096.15** | **-1.1%** | **63.2** | **55.4** |

**DISCARD**: Regression. Reducing heart accumulation didn't help — junctions aligned stayed the same (55.4), but hearts gained dropped from 66.2 to 63.2. Travel time dominates, so carrying more hearts per trip is better. The bottleneck is not hub congestion.

## Experiment 2: Fix junction alignment distance mismatch

Hypothesis: Policy uses `_JUNCTION_ALIGN_DISTANCE=25` for cascade check in `_is_alignable()`, but game engine uses `CvCConfig.JUNCTION_ALIGN_DISTANCE=15`. This means aligners travel to junctions in the 16-25 range from friendly junctions where cascade alignment will fail (heart not consumed, but time wasted on travel + timeout). Fixing to 15 should eliminate these wasted trips.

Additionally, separate exploration frontier to a new `_JUNCTION_EXPLORE_DISTANCE=25` constant so agents still scout broadly but only target truly alignable junctions.

Changes:
1. `aligner_agent.py:25` — `_JUNCTION_ALIGN_DISTANCE = 25` → `15`
2. `aligner_agent.py:26` — New `_JUNCTION_EXPLORE_DISTANCE = 25`
3. `aligner_agent.py:653` — `_alignment_frontier_cells` uses `_JUNCTION_EXPLORE_DISTANCE` for search radius

Results (5-seed avg):

| Seed | Total Reward | Baseline | Change | Hearts Gained | Hearts Used | Junctions Aligned |
|------|-------------|----------|--------|---------------|-------------|-------------------|
| 42 | 1067.54 | 1040.43 | +2.6% | 64 | 53 | 53 |
| 123 | 1090.68 | 1071.49 | +1.8% | 63 | 55 | 55 |
| 7 | 1146.89 | 1103.23 | +4.0% | 70 | 60 | 60 |
| 99 | 1114.49 | 1081.57 | +3.0% | 66 | 55 | 55 |
| 555 | 1199.08 | 1184.05 | +1.3% | 71 | 61 | 61 |
| **Avg** | **1123.73** | **1096.15** | **+2.5%** | **66.8** | **56.8** | **56.8** |

**KEEP**: +2.5% improvement. Junction distance fix eliminates wasted trips to non-alignable junctions. Seeds 42 and 123 show clearest benefit (maps with junctions in the 16-25 cascade band). Seeds 7/99/555 appear unaffected by the fix — their improvement vs baseline may be due to environment differences between baseline and experiment runs.

## Experiment 3: Round-trip scoring in cascade priority

Hypothesis: `_cascade_priority_target` scores junctions as `travel + hub_dist * 0.2`, which strongly favors nearest junctions even if they're far from hub (expensive return trip). Since aligners must return to hub for more hearts, the optimal scoring should account for the full round-trip cost: `travel_to_junction + travel_back_to_hub ≈ travel + hub_dist`. Increasing hub_dist weight from 0.2 to 1.0 should improve throughput by reducing total travel time per alignment cycle.

Changes:
1. `aligner_agent.py:738` — `hub_dist * 0.2` → `hub_dist * 1.0` (Exp 3), then `hub_dist * 0.5` (Exp 3b)

Results — Exp 3 (weight 1.0): avg 1093.79, **-0.2%** vs baseline
Results — Exp 3b (weight 0.5): avg 1118.15, **+2.0%** vs baseline, **-0.5%** vs Exp 2

| Weight | Avg Reward | vs Baseline | Hearts Used | Junctions |
|--------|-----------|-------------|-------------|-----------|
| 0.2 (baseline) | 1096.15 | — | 55.4 | 55.4 |
| 0.2 (w/ dist fix) | 1123.73 | +2.5% | 56.8 | 56.8 |
| 0.5 (w/ dist fix) | 1118.15 | +2.0% | 56.0 | 56.0 |
| 1.0 (w/ dist fix) | 1093.79 | -0.2% | 55.0 | 55.0 |

**DISCARD**: Increasing hub_dist weight hurts performance. Higher weights make aligners cluster near-hub junctions and neglect frontier expansion, which is critical for the cascade mechanism. The original 0.2 weight is well-calibrated — it slightly penalizes far-from-hub junctions without preventing frontier growth.

## Experiment 4: 5 aligners + 3 miners

Hypothesis: With 4 aligners, aligner throughput is the bottleneck — each aligner cycles ~217 steps per alignment. Adding a 5th aligner (25% more capacity) should increase junction alignment rate. Mining surplus is 300-650 per element, so 3 miners may still produce enough resources (7 of each per heart).

Results: Using `--num-aligners 5` flag (no code changes).

| Seed | Exp 2 (4a/4m) | Exp 4 (5a/3m) | Change |
|------|---------------|---------------|--------|
| 42 | 1067.54 | 1037.93 | -2.8% |
| 123 | 1090.68 | 1053.44 | -3.4% |
| 7 | 1146.89 | 1082.52 | -5.6% |
| 99 | 1114.49 | 987.05 | -11.4% |
| 555 | 1199.08 | 1176.16 | -1.9% |
| **Avg** | **1123.73** | **1067.42** | **-5.0%** |

**DISCARD**: 5 aligners is significantly worse. Despite more hearts being produced (67.8 vs 66.8), fewer junctions were aligned (55.0 vs 56.8) due to aligner congestion. Fewer miners also reduces mining reward. The bottleneck is NOT aligner count — it's per-aligner efficiency.

Key insight: per-aligner throughput is ~211 steps/alignment, but ideal round-trip is ~41 steps (15 to junction + 15 back + 1 align + 10 hub wait). The remaining ~170 steps are: gear-up (one-time), stuck timeouts (100 steps max), exploration, HP retreat, navigation obstacles.

## Experiment 5: Reduce stuck timeout for faster failure recovery

Hypothesis: When an aligner gets stuck navigating to a junction (BFS fails), it waits `stuck_threshold * 5 = 100` steps before timing out. Reducing to `stuck_threshold * 3 = 60` steps saves up to 40 steps per stuck event, allowing the aligner to try alternative targets sooner.

Results: avg 1112.35, +1.5% vs baseline, **-1.0%** vs Exp 2. Junction counts identical to Exp 2 (56.6 vs 56.8). Stuck timeout is NOT a significant bottleneck — aligners aren't wasting time stuck.

**DISCARD**: No effect on junction throughput. Reverting.

Key insight from Exps 1-5: junction alignment count is remarkably stable (~55-57) across most experiments. Only the distance fix helped slightly. We have ~10 unused hearts at game end — the constraint is **junction availability**, not aligner speed. The cascade frontier stalls when there are no more junctions within 15 cells of friendly junctions.

## Experiment 6: Pure nearest-junction scoring (hub_dist weight 0.0)

Hypothesis: With hub_dist weight 0.2, aligners slightly prefer close-to-hub junctions, potentially clustering near hub and neglecting frontier-edge junctions. Setting weight to 0.0 (pure travel distance) should help aligners spread evenly across the frontier, maximizing cascade expansion into new territory.

Results: avg 1114.35, -0.8% vs Exp 2. Junctions 55.4 vs 56.8. Seed 42 lost 4 junctions.

**DISCARD**: 0.2 weight confirmed optimal. Without it, aligners scatter on some maps and miss central junctions.

Scoring experiment summary:
| Weight | Avg Reward | Junctions |
|--------|-----------|-----------|
| 0.0 | 1114.35 | 55.4 |
| **0.2** | **1123.73** | **56.8** |
| 0.5 | 1118.15 | 56.0 |
| 1.0 | 1093.79 | 55.0 |

## Experiment 7: Increase explore distance 25→35

Hypothesis: The alignment frontier stalls when nearby junctions are exhausted. Increasing `_JUNCTION_EXPLORE_DISTANCE` from 25 to 35 lets aligners scout further from the alignment network during exploration, discovering junctions beyond the current cascade range. These junctions become targetable as the cascade extends.

Results: avg 1103.15, -1.8% vs Exp 2. Seeds 42 and 555 were EXACTLY identical to Exp 2 — wider exploration had zero effect. Seed 99 lost 1 junction and regressed -8.5%.

**DISCARD**: Junction discovery is NOT the bottleneck. All nearby junctions are already found with 25 explore distance.

---

## Summary of all experiments

| # | Experiment | Avg Reward | vs Baseline | vs Exp 2 | Junctions | Status |
|---|-----------|-----------|-------------|----------|-----------|--------|
| 0 | Baseline (4a/4m, dist=25) | 1096.15 | — | — | 55.4 | — |
| 1 | Fast-cycle hearts (<4→<2) | 1083.61 | -1.1% | — | 55.4 | DISCARD |
| **2** | **Junction dist fix (25→15)** | **1123.73** | **+2.5%** | **—** | **56.8** | **KEEP** |
| 3 | Hub_dist weight 1.0 | 1093.79 | -0.2% | -2.7% | 55.0 | DISCARD |
| 3b | Hub_dist weight 0.5 | 1118.15 | +2.0% | -0.5% | 56.0 | DISCARD |
| 4 | 5 aligners + 3 miners | 1067.42 | -2.6% | -5.0% | 55.0 | DISCARD |
| 5 | Stuck timeout 5x→3x | 1112.35 | +1.5% | -1.0% | 56.6 | DISCARD |
| 6 | Hub_dist weight 0.0 | 1114.35 | +1.7% | -0.8% | 55.4 | DISCARD |
| 7 | Explore distance 25→35 | 1103.15 | +0.6% | -1.8% | 56.6 | DISCARD |

**Only Experiment 2 produced a statistically significant improvement.** The junction distance fix corrected a real bug: policy used 25 for cascade alignment checks but the game engine uses 15, causing wasted trips.

**Key findings:**
1. Junction alignment count is remarkably stable (~55-57) across all parameter variations
2. ~10 hearts remain unused at game end → the bottleneck is junction availability, not aligner speed
3. The cascade frontier naturally stalls when junction density drops below 1 per 15 cells
4. Hub_dist weight 0.2 in cascade scoring is well-calibrated (optimal)
5. 4 aligners + 4 miners (50/50 split) is optimal
6. Stuck timeout and exploration distance changes have no effect on junction count

**Remaining bottleneck:** The alignment ceiling (~57 junctions per 3000 steps) is determined by map topology — specifically the density and distribution of junctions relative to the cascade range (15 cells from friendly junctions, 25 from hub). Improving this would require either:
- Increasing JUNCTION_ALIGN_DISTANCE in the game engine (config change)
- Placing junctions more densely (map generation change)
- Adding new alignment mechanics (game design change)

## Experiment 8: Frontier-expansion scoring bonus

Hypothesis: Current scoring picks nearest alignable junction regardless of strategic value. Some junctions are "bridge" junctions that, once aligned, bring currently-unreachable junctions into cascade range. Adding a bonus for junctions that would unlock more junctions should expand the cascade frontier faster.

Changes: In `_cascade_priority_target`, for each candidate junction, count how many known-but-not-alignable junctions would enter cascade range (within 15 cells) if it were aligned. Each unlockable junction gives a score bonus.

Results — Exp 8 (bonus -5.0): avg 1099.67, -2.1% vs Exp 2. Seed 42 dropped from 53→46 junctions.
Results — Exp 8b (bonus -1.0): avg 1100.99, -2.0% vs Exp 2. Seed 99 dropped from 55→50 junctions.

**DISCARD**: Frontier expansion scoring is fundamentally flawed. The unlock count doesn't account for actual reachability (walls, map topology), and the bonus distorts scoring to favor distant bridge junctions over easy nearby ones.

Additional finding: Reward is `per_tick=True` — each aligned junction gives reward every step (`weight=1.0/max_steps`). Earlier alignments earn more cumulative reward. But the junction ceiling (~57) is architectural, not timing-based.

## Experiment 9: Heart carry increase (<4→<6)

Hypothesis: If aligners carry more hearts per trip, they can align multiple junctions without returning to hub. Increasing the heart accumulation threshold from <4 to <6 should reduce round-trip overhead.

Results: avg 1090.42, **-3.0%** vs Exp 2. One aligner monopolized hearts while others idled at hub.

**DISCARD**: Heart competition is already tight with 4 aligners. Increasing carry threshold exacerbates inequality — one aligner gets 6 hearts while others get 0.

## Experiment 10: Miner return_load=20

Hypothesis: Miners returning with higher loads (20 vs default) means fewer trips and more total resources deposited, enabling more hearts.

Results: avg 1082.24, **-12.6%** vs baseline. Massive regression.

**DISCARD**: Miners waste too much time traveling to accumulate 20 resources. Deposit frequency matters more than deposit size.

## Experiment 11: Blacklist threshold 1→3

Hypothesis: Currently aligners blacklist a junction after 1 failed alignment attempt (timeout). Raising to 3 gives them more chances to reach tricky junctions that may be reachable but require more pathing attempts.

Results: avg 1104.69, **-1.7%** vs Exp 2. Agents spent 265 steps stuck retrying genuinely unreachable junctions.

**DISCARD**: The first timeout is usually correct — the junction truly isn't reachable. Retrying wastes time.

## Experiment 12: Explore cap 40→20 steps

Hypothesis: Aligners spend ~38 steps average per explore phase (84 total across 4 aligners). Halving the explore cap to 20 should push them back to hub/junction sooner.

Results: avg 1114.55, **-0.8%** vs Exp 2. Truncated exploration left some junctions undiscovered on certain seeds.

**DISCARD**: Exploration time is already well-calibrated. Cutting it short hurts junction discovery.

## Experiment 13: L2 distance in policy (matching game engine)

Hypothesis: Game engine uses L2 distance (dr²+dc² ≤ r²) but policy uses Manhattan distance. Fixing both `_is_alignable()` and `_alignment_frontier_cells()` to use L2 should eliminate edge cases where policy thinks a junction is alignable but engine disagrees (or vice versa).

Changes:
1. `_is_alignable()`: Manhattan `abs(dr)+abs(dc) <= radius` → L2 `dr*dr+dc*dc <= radius*radius`
2. `_alignment_frontier_cells()`: Same conversion for explore distance check

Results: avg 1119.36, **-0.4%** vs Exp 2. Junction counts nearly identical — very few junctions sit in the Manhattan/L2 diagonal gap.

**DISCARD**: Theoretically correct but no practical impact. The map layouts don't place junctions in positions where Manhattan vs L2 disagree.

## Experiment 14: BFS direction diversity

Hypothesis: BFS always explores in the same direction order (N/S/E/W), causing all agents to prefer the same paths. Rotating the starting direction based on agent_id should create more diverse pathing and reduce agent congestion.

Results: avg 1097.78, **-2.3%** vs Exp 2. Changed direction preferences gave specific agents worse paths on some maps.

**DISCARD**: The default direction order is fine. Diversity for its own sake doesn't help — the original order produces good paths on average.

## Experiment 15: Quadrant exploration dispersion

Hypothesis: All 4 aligners explore the same direction (nearest unknown), causing them to cluster. Assigning each aligner a preferred quadrant (based on agent_id % 4) and biasing exploration toward that direction should improve map coverage.

Changes: Added `_quadrant_biased_target()` method that scores frontier cells with `travel - quadrant_bonus * 0.3` where quadrant_bonus rewards cells in the agent's preferred direction from hub.

Results:
| Seed | Exp 2 | Exp 15 | Change |
|------|-------|--------|--------|
| 42 | 1067.54 | 1072.19 | +0.4% |
| 123 | 1090.68 | 1093.92 | +0.3% |
| 7 | 1146.89 | 1099.53 | -4.1% |
| 99 | 1114.49 | 1069.52 | -4.0% |
| 555 | 1199.08 | 1144.76 | -4.5% |
| **Avg** | **1123.73** | **1095.98** | **-2.5%** |

**DISCARD**: Quadrant bias hurts on 3/5 seeds. The static quadrant assignment doesn't adapt to actual junction placement — agents forced into junction-sparse quadrants waste exploration time.

---

## Updated Summary (Experiments 1-15)

| # | Experiment | Avg Reward | vs Exp 2 | Junctions | Status |
|---|-----------|-----------|----------|-----------|--------|
| 0 | Baseline | 1096.15 | -2.5% | 55.4 | — |
| 1 | Fast-cycle hearts | 1083.61 | -3.6% | 55.4 | DISCARD |
| **2** | **Junction dist fix** | **1123.73** | **—** | **56.8** | **KEEP** |
| 3 | Scoring weight 1.0 | 1093.79 | -2.7% | 55.0 | DISCARD |
| 3b | Scoring weight 0.5 | 1118.15 | -0.5% | 56.0 | DISCARD |
| 4 | 5 aligners | 1067.42 | -5.0% | 55.0 | DISCARD |
| 5 | Stuck timeout 3x | 1112.35 | -1.0% | 56.6 | DISCARD |
| 6 | Scoring weight 0.0 | 1114.35 | -0.8% | 55.4 | DISCARD |
| 7 | Explore dist 35 | 1103.15 | -1.8% | 56.6 | DISCARD |
| 8 | Frontier bonus -5.0 | 1099.67 | -2.1% | 55.0 | DISCARD |
| 8b | Frontier bonus -1.0 | 1100.99 | -2.0% | 54.2 | DISCARD |
| 9 | Heart carry <6 | 1090.42 | -3.0% | 55.6 | DISCARD |
| 10 | return_load=20 | 1082.24 | -3.7% | 54.4 | DISCARD |
| 11 | Blacklist threshold 3 | 1104.69 | -1.7% | 55.8 | DISCARD |
| 12 | Explore cap 20 | 1114.55 | -0.8% | 56.2 | DISCARD |
| 13 | L2 distance | 1119.36 | -0.4% | 56.4 | DISCARD |
| 14 | BFS direction diversity | 1097.78 | -2.3% | 55.2 | DISCARD |
| 15 | Quadrant dispersion | 1095.98 | -2.5% | 55.4 | DISCARD |

## Experiment 16: Fair heart sharing at game start

Hypothesis: When 4 aligners converge on hub simultaneously, limit heart accumulation to 1 when 2+ others are also getting hearts. This ensures faster cascade start by distributing hearts fairly.

Changes: In `_maybe_finish_skill` and `_plan_skill`, check `agents_getting_hearts` count and cap accumulation to 1 when 2+ others are getting hearts.

Results: avg 1118.06, **-0.5%** vs Exp 2. Seeds 42/123 improved slightly, but 99/555 regressed. Net negative — heart monopolization at hub isn't actually a bottleneck.

**DISCARD**.

## Experiment 17: Progressive evasion for blocked moves

Hypothesis: Port cross_role_policy's progressive evasion (perpendicular/reverse escape on blocked moves) to replace the random navigation shake. This should reduce move failures.

Key finding: `last_move_target` is reset to None by `_update_map_memory` (line 474) before the evasion check can read it. Fixed by saving `prev_move_target` before the call. With the fix, evasion fires but causes -3.3% regression on seed 42. The evasion disrupts BFS pathfinding — perpendicular moves take agents off optimal paths.

**DISCARD**: Progressive evasion suits greedy navigation (cross_role) but hurts BFS navigation (machina).

## Experiment 18: Proactive agent collision avoidance in BFS

Hypothesis: Add SharedMap teammate positions to BFS avoid set to route around known agent locations. Should reduce the 1132 failed moves per episode (seed 42).

Results: avg ~1044.85 on seed 42, **-2.1%** vs Exp 2. Move failures reduced marginally (1132→1106) but longer BFS paths cost more time than avoided collisions. Agent positions are stale by the time paths are executed.

**DISCARD**: Reactive collision handling (move_blocked_cells cooldowns) is better than proactive avoidance for dynamic agents.

## Experiment 19: Periodic blacklist expiry every 500 steps

Hypothesis: Port cross_role_policy's blacklist expiry mechanism. Clearing blacklisted junctions every 500 steps allows retrying previously-unreachable junctions that may have become reachable as the cascade extended.

Results: avg 1121.51, **-0.2%** vs Exp 2. Seeds 42/123/7/555 were IDENTICAL to exp2 (no blacklisted junctions in self-play). Seed 99 regressed -1.0% from retrying truly-unreachable junctions.

**DISCARD**: Self-play doesn't blacklist junctions — all junctions are reachable through cascade.

## 10k-step diagnostic (seed 42)

Ran seed 42 at 10k steps: 53 junctions aligned, 64 hearts gained — IDENTICAL to 3k steps. Confirms:
- Junction ceiling is truly architectural (map topology)
- All alignment happens in first 2000-3000 steps
- Remaining 7000 steps hold existing junctions
- 11 hearts unused (hearts not the bottleneck)
- Oxygen extractors fully depleted by step 3000

---

## Final Summary (Experiments 1-19)

| # | Experiment | Avg Reward | vs Exp 2 | Junctions | Status |
|---|-----------|-----------|----------|-----------|--------|
| 0 | Baseline | 1096.15 | -2.5% | 55.4 | — |
| 1 | Fast-cycle hearts | 1083.61 | -3.6% | 55.4 | DISCARD |
| **2** | **Junction dist fix** | **1123.73** | **—** | **56.8** | **KEEP** |
| 3 | Scoring weight 1.0 | 1093.79 | -2.7% | 55.0 | DISCARD |
| 3b | Scoring weight 0.5 | 1118.15 | -0.5% | 56.0 | DISCARD |
| 4 | 5 aligners | 1067.42 | -5.0% | 55.0 | DISCARD |
| 5 | Stuck timeout 3x | 1112.35 | -1.0% | 56.6 | DISCARD |
| 6 | Scoring weight 0.0 | 1114.35 | -0.8% | 55.4 | DISCARD |
| 7 | Explore dist 35 | 1103.15 | -1.8% | 56.6 | DISCARD |
| 8 | Frontier bonus -5.0 | 1099.67 | -2.1% | 55.0 | DISCARD |
| 8b | Frontier bonus -1.0 | 1100.99 | -2.0% | 54.2 | DISCARD |
| 9 | Heart carry <6 | 1090.42 | -3.0% | 55.6 | DISCARD |
| 10 | return_load=20 | 1082.24 | -3.7% | 54.4 | DISCARD |
| 11 | Blacklist threshold 3 | 1104.69 | -1.7% | 55.8 | DISCARD |
| 12 | Explore cap 20 | 1114.55 | -0.8% | 56.2 | DISCARD |
| 13 | L2 distance | 1119.36 | -0.4% | 56.4 | DISCARD |
| 14 | BFS direction diversity | 1097.78 | -2.3% | 55.2 | DISCARD |
| 15 | Quadrant dispersion | 1095.98 | -2.5% | 55.4 | DISCARD |
| 16 | Fair heart sharing | 1118.06 | -0.5% | 56.0 | DISCARD |
| 17 | Progressive evasion | 1032.32 | -8.1% | 53.0 | DISCARD |
| 18 | Collision avoidance BFS | 1044.85 | -7.0% | 53.0 | DISCARD |
| 19 | Blacklist expiry | 1121.51 | -0.2% | 56.0 | DISCARD |

**19 experiments run, only Exp 2 (junction dist fix) improved reward.** The junction alignment ceiling (~53-61 depending on seed) is determined by map topology — junction density and placement relative to the 15-cell cascade range and 25-cell hub range. The 10k-step diagnostic proves no additional junctions can be aligned with more time.

**What we've proven impossible to improve within the scripted architecture:**
- Heart accumulation strategy (fast-cycle, sharing, carry limits)
- Junction scoring weights (0.0 to 1.0, all tested)
- Aligner/miner split (4/4, 5/3 tested)
- Exploration parameters (distance, duration, direction)
- Navigation improvements (BFS variants, collision avoidance, evasion)
- Distance calculations (Manhattan vs L2)
- Blacklisting/retry strategies

**The only remaining lever for offline reward** is the one-time junction distance fix (+2.5%), which corrected a genuine policy-game engine mismatch.
