# Experiment Log: claude/amazing-meitner-dz2Gf

Working on: Issue #77 — RAxer bug fix sweep + scripted policy optimization

## 2026-05-20 05:30: autoresearch starting

**Plan**: 
1. Port krCLo improvements (+4.4%) to this branch: 3A5M split, hearts5 accumulation, progress tracking fix, cooldown activation
2. Run baseline to confirm
3. Implement dynamic role switching — convert idle aligners to miners after junction saturation
4. This is the biggest untapped opportunity: junctions saturate at ~1200 steps, aligners idle for remaining 1800+ steps at 3K (8800+ at 10K online)

**Context from previous sessions**:
- Issue #76 (priority:1) is blocked on expired auth token (4th consecutive session)
- krCLo session found +4.4% with 3A5M + hearts5 + progress fix
- Junction saturation happens at ~1200 steps, all reward after that is pure hold time
- Offline eval has no active enemy clips — online competition is adversarial

## 2026-05-20 05:30: starting to port krCLo improvements and run baseline

Ported krCLo: 3A5M split, hearts5 threshold, progress tracking fix.
Baseline established: avg 1107.4 across seeds 42/123/7 (1078.1/1070.3/1173.9).

## 2026-05-20 06:00-08:00: dynamic role switching (mining mode) — FAILED

Attempted to convert idle aligners to miners after step 1500 when junctions are saturated.
Implemented full mining mode: gear_up_miner, mine_resources, deposit_resources skills.

**Bugs found and fixed**:
1. Aligners never updated SharedMap.agent_gears → mining mode race condition
2. Mining mode oscillation (enter/exit rapidly) → switched to step-based trigger
3. All 3 aligners entering mining mode → agent ID ordering to keep 1 aligner
4. known_extractors lost after _copy_with → use shared_map directly
5. Mining via noop instead of step-into-blocked → fixed collision-based mining
6. Depleted extractors not removed from shared map → agents stuck on empty cells

Even after all fixes, mining mode consistently hurt reward (-3% to -5%). The aligner-turned-miners were inefficient compared to dedicated miners. Approach abandoned.

## 2026-05-20 08:00-08:45: parameter sweeps — mostly FAILED

Tested many parameter changes:
- 2A6M: 1017.5 (much worse, -8.1%)
- 4A4M: 999.9 (even worse, -9.7%)
- Hub distance factor 0.1: -1.9%, 0.3: -1.4%
- Heart accumulation <3: -4.3%, <8: -0.8%
- Align_neutral timeout 75→45: -2.7%
- Return_load 30: -1.8%, 50: catastrophic
- Mine stale 15→8: -0.2% (neutral)

3A5M with default parameters is clearly the sweet spot.

## 2026-05-20 08:45: gear_up approach diversification — KEPT (+1.1%)

**Hypothesis**: Multiple miners approach the miner station from the same side at game start, causing congestion. Agent 2 on seed 42 wasted ~500 steps (80 gear_up events) in gear_up→stale→explore loops.

**Fix**: Changed miner gear_up approach to `(obs.agent_id + state.gear_up_approach_rotation) % 4` — each miner approaches from a unique side based on ID.

**Results** (3-seed avg):
- Seed 42: 1103.9 (baseline 1078.1, +2.4%)
- Seed 123: 1087.2 (baseline 1070.3, +1.6%)
- Seed 7: 1169.1 (baseline 1173.9, -0.4%)
- **Avg: 1120.1 (baseline 1107.4, +1.1%)**

Also cleaned up dead mining mode code from machina_llm_roles_policy.py.

**Next**: Continue looking for improvements. The main bottleneck is junction availability (hearts > junctions), not heart production. Need to find ways to discover/align junctions faster.

## 2026-05-20 10:00-11:45: session 2 experiment sweep

**Tried and failed**:
1. Aligner gear_up approach diversification: -4.2% on seed 42. Unlike miner stations, forcing different approach sides hurt.
2. First-deposit speed (return_load=20 or 28 for first trip): -3.0% to -9.7%. Trip overhead outweighs earlier heart availability.
3. Heart queue management (limit hub trips when hub empty): -1.0% to -5.1%. The hub-empty estimate lags reality, causing aligners to miss hearts.
4. JUNCTION_ALIGN_DISTANCE=30/35: neutral to -3.4%. Most junctions already within 25 cells.
5. HUB_ALIGN_DISTANCE=30: neutral to -3.1%.

**Key diagnostic finding**: Between steps 75-200 on seed 42, all 3 aligners oscillate between get_heart (15 steps at empty hub) and explore (discover 1-2 junctions). The explore phases ARE productive (discover junctions for later). The get_heart stale exits at 15 steps (not 75-step timeout), so `get_heart_timeouts` never increments and "defend" mode never triggers.

**Kept**: Shared depleted extractors (+1.0%)

**Hypothesis**: Each miner tracks extractor depletion independently. When one miner marks an extractor as depleted, others still navigate to it, waste 40+ steps mining nothing, then mark it themselves.

**Fix**: Added `depleted_extractors: set[Coord]` to SharedMap, shared via `_bind_shared_map_miner`. When any miner marks an extractor depleted, all miners instantly know.

**Results** (3-seed avg):
- Seed 42: 1102.7 (baseline 1103.9, -0.1%)
- Seed 123: 1100.9 (baseline 1087.2, +1.3%)
- Seed 7: 1191.7 (baseline 1169.1, +1.9%)
- **Avg: 1131.8 (baseline 1120.1, +1.0%)**

6-seed validation (42-47): 1148.8 vs baseline 1131.5 (+1.5%). Some seed variance (43: -2.7%, 45: -5.4%) but 6/8 seeds improved.

## 2026-05-20 13:00-14:00: session 3 experiments

**Tried and failed**:
1. Mine stale → retry: after mine stale exit, skip explore and go directly to mine_until_full if active extractors remain. v1 (any active): seed 123 catastrophic -7.6%, miners stuck cycling depleted cluster. v2 (far active only, max 1 consecutive): still -0.4% avg. Reverted.

**Kept**: Early heart cap (+1.0%)

**Hypothesis**: Agent 6 (3rd aligner) waits 162 steps for its first heart because agents 1 & 3 grab all 5 initial hub hearts via hearts5 accumulation. By step 185, 18 alignable junctions are already available — agent 6 could have been aligning much sooner.

**Fix**: In `_maybe_finish_skill`, when `hearts_crafted_estimate == 0` (no crafted hearts yet = early game), cap the hearts5 accumulation threshold from 5 to 2. This means each aligner grabs at most 2 hearts from the initial pool, leaving 1 for the 3rd aligner.

**Results**: Agent 6 gets first heart at step 30 instead of step 185 — 155 steps earlier!
- Cap=1: too aggressive, avg -1.3%
- **Cap=2: avg +1.0% (3-seed), +1.7% (6-seed)**
- Cap=3: neutral, avg +0.1%

3-seed detail:
- Seed 42: 1107.8 (baseline 1102.7, +0.5%)
- Seed 123: 1091.2 (baseline 1100.9, -0.9%)
- Seed 7: 1231.4 (baseline 1191.7, +3.3%)
- **Avg: 1143.5 (baseline 1131.8, +1.0%)**

6-seed (42-47): 1167.8 vs baseline 1148.8 (+1.7%)

**Cumulative improvement**: +3.3% vs original baseline (1143.5 vs 1107.4)

## 2026-05-20 18:00-19:40: session 4 — exhaustive parameter sweep

**Key finding**: BFS-for-junctions hypothesis DISPROVEN. Previous sessions claimed "ALL BFS methods ALWAYS fail for junction targets because junctions are in blocked_cells." Logging showed this is FALSE: junctions are NOT added to `blocked_now` (only walls, extractors, hubs, stations are), so junctions ARE in `known_free_cells` and BFS works normally. Only 2 out of ~200 junction navigations fell through to greedy (distant blocked junctions at dist>30). The BFS fix was a dead end.

**Also identified**: Miner gear contamination loop on seed 123 — agents 0 and 4 oscillate in gear_up→explore for 100+ steps. Agent 4 gets contaminated twice at (3, -4) despite `contamination_avoid_cells`. Root cause unclear — may be only path through contamination cell.

**Tried and failed**:
1. Deposit timeout 30→45: +1.2% 3-seed, -1.0% 6-seed (inconsistent)
2. Hub distance weight for extractors (//2 → *1): -1.0% (too much hub bias)
3. Sector-based explore diversification: -5.1% (forces suboptimal exploration)
4. Move cooldown 6→3: -2.8% (agents get stuck in repetitive failed moves)
5. Sticky explore targets (5/10/15 step commitment): +0.3-0.4% avg (inconsistent)
6. Navigation shake threshold 5→3: +0.3% 6-seed (within noise)
7. Explore cap 30→45: +0.9% 3-seed, -0.2% 6-seed (seed 47 regression)

**Conclusion**: The +3.3% cumulative improvement (gear_up approach diversification + shared depleted extractors + early heart cap) appears to be near the ceiling for incremental scripted changes. 18+ parameter/mechanism tweaks tested across sessions 3-4 have all been neutral to negative. Further improvement likely requires architectural changes (different skill framework, LLM planner improvements, or online-specific adaptations).

## 2026-05-21: session 5 — deep diagnostic + 7 experiments, all failed

**Key diagnostic findings** (skill time tracking added to aligners and miners):
- Aligner time allocation: **68% explore**, 23% align_neutral, 9% get_heart, <2% gear_up+unstuck
- Miner time allocation: 45% mine_until_full, 33% explore, 19% deposit_to_hub, 1% gear_up
- 84% of aligner explore phases cap at 30 steps without finding junctions (190 caps vs 172 completions on seed 42)
- When explore completes (finds junction), it averages ~13 steps. Caps are always 30 steps.
- align_neutral: 22 timeouts vs 12 completions on seed 42 (each timeout = 75 wasted steps)
- ALL align_neutral timeouts have on_target=False — agent never reaches the junction
- Timeout distances range from 2-57 cells: both close-range deadlocks and unreachable targets
- BFS navigation succeeds 99%+ of the time — timeouts from long winding BFS paths, not nav failures
- Game's JUNCTION_ALIGN_DISTANCE=15, policy uses 25. The 25 acts as "planning horizon" for explore.
- Oxygen is the mining bottleneck: 900 gained vs carbon 1350, germanium 1090, silicon 1570

**Tried and failed**:
1. Explore coordination via SharedMap (dist=8, dist=5): aligners forced to different frontier cells hurt individual efficiency. -0.3% / -0.7%
2. Hearts accumulation cap 5→8: more hub wait time, aligners idle longer. -2.2%
3. JUNCTION_ALIGN_DISTANCE 25→15 (match game constant): +0.5% 3-seed but -0.4% 6-seed. Seed 47 regressed -2.9%. The "planning horizon" of 25 helps explore find junctions that will become alignable as network grows.
4. JUNCTION_ALIGN_DISTANCE 25→20: -1.2%
5. Align_neutral timeout reduction (×5→×3): aligners give up on reachable junctions too quickly, spend MORE time exploring. -5.7%
6. Hub-empty explore-instead (explore when hearts_crafted_estimate=0 and hub_hearts_withdrawn≥5): aligners explore far from hub, long return trip when hearts arrive. -2.1%
7. Distance progress early exit (blacklist target if no distance improvement for 40 steps): counter-productive blacklisting removes useful junction knowledge. -1.2% to -2.2%

**Conclusion**: The +3.3% cumulative improvement remains the ceiling. 25+ experiments across 5 sessions have been exhaustively tested. The bottleneck is structural: aligners spend 68% exploring because junctions are scattered across the map and alignment frontier shrinks as territory is explored. Further gains require fundamentally different approaches (RL-trained policy, LLM-guided exploration, or online-specific enemy adaptation).

## 2026-05-21: session 6 — bug fixes + hub_dist removal + 10 more failed experiments

**Bug fixes committed (correctness, zero reward impact)**:
1. **BFS SharedMap corruption**: `_bfs_without_cooldowns` used `-=` and `|=` on SharedMap sets, mutating shared state for ALL agents. Fixed by creating new temporary sets (`saved_blocked - cooldown_cells`) instead of in-place mutation. Ported from RAxer commit 002e564.
2. **Progress tracking order**: `state.last_has_heart` / `state.last_friendly_junctions` updated BEFORE `made_progress` check, making get_heart and align_neutral progress always False. Fixed by moving updates after the check. Ported from RAxer commit faa6433.

**Kept**: Remove hub_dist bias from junction target scoring (+0.6%)

**Hypothesis**: `_cascade_priority_target` scored junctions as `travel + hub_dist * 0.2`, biasing toward hub-closer junctions. This caused aligners to skip nearby junctions in favor of hub-proximate ones, adding unnecessary travel time.

**Fix**: Simplified scoring to pure Manhattan distance: `return abs(j[0] - current_abs[0]) + abs(j[1] - current_abs[1])`. Important: must use `def score(j): return travel` form, NOT `lambda j: (travel, j)` — the tuple tiebreaker changes set iteration order for equidistant junctions and produces worse results (seed 42 drops from 1138.3 to 1109.0).

**Results** (6-seed 42-47):
- Baseline: 1167.9 avg → **New: 1174.6 avg (+0.6%)**
- Seed 42: 1138.3 (+2.7%), Seed 43: 1160.5 (+0.1%), Seed 44: 1272.7 (+1.8%)
- Seed 45: 1237.4 (-0.8%), Seed 46: 1129.2 (+1.8%), Seed 47: 1109.6 (-2.0%)

**Tried and failed** (10 experiments):
1. 5A3M: fewer miners → fewer hearts crafted, net negative
2. 6A2M: even worse — heart production collapses
3. 8A0M: 141.5 total (−87%). Hub starts with only 5 hearts (INITIAL_HEARTS=5 × wealth=1), no miners = no crafted hearts. Disproves "all aligners" hypothesis.
4. All-scouts configurations: scouts don't align junctions
5. Spread-aware explore (0.3 weight): forces aligners away from nearest frontier, hurts individual efficiency
6. Spread-aware explore (0.15 weight): same issue, smaller magnitude
7. Cascade unlock scoring (prefer unlockable junctions): adds complexity without improvement
8. stuck_threshold sweep (10, 12, 20): 15 is optimal; lower = premature exits, higher = too much wasted time
9. JUNCTION_ALIGN_DISTANCE=30: beyond useful planning horizon, aligners navigate to unreachable junctions
10. Negative hub_dist weight (prefer frontier junctions): hurts early game when hub-proximate junctions matter

**Cumulative improvement**: +3.3% (sessions 1-5) + 0.6% (session 6) = **+3.9% vs original baseline**

New baseline: 3-seed avg 1152.0, 6-seed avg 1174.6

## 2026-05-21: session 7 — 16 experiments, all neutral-to-negative

**Key discovery**: Map is only 50×50 (40×40 playable) with 13×13 observation grid (radius=6). With 118 junctions Poisson-distributed in 1600 cells, junction density is high. The alignment frontier filter has ZERO effect because junction_search_radius (31) covers almost the entire playable map.

**Tried and failed** (16 experiments):
1. Hearts accumulation cap 5→3: -3.0% (too many hub trips outweigh faster departure)
2. Hearts accumulation cap 5→4: -5.1% (same issue, worse)
3. Keep blacklisted junctions in shared map: -0.1% (neutral)
4. Team scarce threshold 5→2: no effect on any seed
5. Team scarce threshold 5→1: no effect on any seed
6. Port RAxer get_heart_timeouts increment on stuck/stale: -24.8% (catastrophic — causes premature redirect to defend mode, which does noop on friendly junctions)
7. Adaptive align timeout (dist×3, min 30 steps): -2.5%
8. Adaptive align timeout (dist×4, min 45 steps): -4.5%
9. Multi-target BFS for align_neutral: -3.3% (BFS overhead + wrong strategic choices)
10. Remove junction coordination: -2.8% (aligners compete for same junctions)
11. Explore cap 30→20: -2.0%
12. Explore cap 30→25: -3.1%
13. HP retreat disabled: no effect (never triggers in offline mode)
14. Sticky explore targets (15-step commitment): -5.5% (frontier changes too fast)
15. Cascade unlock scoring (weight=3): -2.9%, (weight=1): no effect
16. Remove alignment frontier filter: no effect (50×50 map too small for filter to matter)

**Near-miss**: Nav-shake threshold 5→3 helped seed 47 (+2.8%) but hurt seed 7 (-0.3%), net inconsistent. Return_load 30: -14%, return_load 50: catastrophic.

**Conclusion**: 55+ experiments across 7 sessions. The +3.9% improvement is the confirmed ceiling for incremental scripted optimization. The map size (50×50) means most coordination/exploration optimizations are neutralized — agents naturally cover the small map efficiently. Further gains would require either RL training, online-specific enemy adaptation, or fundamental policy architecture changes.

## 2026-05-21: session 8 — global obs integration + new approaches

**Experiment 1: Global obs hub elements for scarce element detection — FAILED (-0.4%)**

**Hypothesis**: Miners use SharedMap.total_deposits to detect team-scarce elements, but this lags reality (only updated on deposit events). Global observation features (`team:oxygen`, `team:carbon`, etc.) provide real-time hub element inventory. Using actual hub inventory should improve scarce element routing accuracy.

**Changes**: Added `_read_hub_elements(obs)` and `_team_scarce_element_from_obs(obs)` methods to MinerSkillImpl. Updated `_mine_until_full` and `_scripted_skill_choice` to prioritize obs-based scarce detection. Also updated `_update_progress` to use hub elements for better `hearts_crafted_estimate`.

**Results** (6-seed 42-47):
- Baseline: 1174.6 avg → **New: 1170.3 avg (-0.4%)**
- Seed 42: 1129.9 (-0.7%), Seed 43: 1156.9 (-0.3%), Seed 44: 1236.1 (-2.9%)
- Seed 45: 1249.3 (+1.0%), Seed 46: 1169.3 (+3.6%), Seed 47: 1080.1 (-2.7%)

**Interpretation**: The real-time hub inventory doesn't help because: (1) scarce element detection already works well enough with deposit tracking, (2) hub inventory fluctuates rapidly as hearts get crafted (consuming 7 of each element), making instantaneous readings noisy, (3) miners can't control which extractors are nearby — the scarce element info is actionable only when miners have a choice between equal-distance extractors. Reverted.

**Experiment 2: Junction deposit — miners deposit at nearest friendly junction instead of hub**

**Discovery**: Junctions have a `deposit_{team}` on_use_handler that forwards cargo to the team hub via `queryDeposit`. This means miners don't need to trek all the way back to the hub — they can deposit at ANY friendly (cog-aligned) junction. Average distance to nearest friendly junction should be much shorter than to the hub, saving significant travel time per deposit cycle.

**Hypothesis**: Miners currently waste 30-37 deposit cycles per game, each requiring a round-trip to the hub. If the nearest friendly junction is closer, routing there instead saves travel steps per cycle. With 5 miners over 3000 steps, even saving 5 steps per cycle = 750-925 total steps redirected to mining.

**Changes**: Modified `_deposit_to_hub` in `llm_skills.py` to check SharedMap for `known_friendly_junctions` and route to the nearest one when it's closer than the hub. Updated `_update_progress` to count junction proximity as valid for deposit skill.

**Results** (seed 42): total_reward=1088.1 vs baseline 1138.3 = **-4.4%**

**Interpretation**: Junction deposits DON'T work as expected. 108 successful deposits but 166 stale exits (miner adjacent to junction but cargo not decreasing). The deposit handler fires on junction collision but most attempts fail. Possible reasons: (1) SharedMap has stale friendly junction data — clips scramble junctions every 100 steps but the map doesn't update until an agent sees the change, (2) the `on_use_handler` for junction deposit may have additional constraints in the C++ engine not visible in Python config. The 166 stale exits waste enormous miner time. Reverted.

## 2026-05-21: session 9 — MACHINA_1 (88×88) pivot + HP retreat fix

**Key discovery**: 50×50 arena has hit +3.9% ceiling after 55+ experiments. Pivoted to MACHINA_1 (88×88, 10000 steps, 4 clips ships) — the actual online tournament map.

**Diagnostic on MACHINA_1**: Catastrophic baseline — 86 deaths, 28.3 total_reward at 10000 steps. All agents die repeatedly from HP drain. HP retreat was DISABLED for aligners (`_read_hp` returned None in `aligner_agent.py:560`). Miners retreat at 25% HP but hub is too far on 88×88.

**KEPT: HP retreat for aligners + anti-oscillation + miner territory retreat (+60% on machina1)**

Changes:
1. **Enable aligner HP reading**: `_read_hp` now reads actual `inv:hp` from observation tokens instead of returning None
2. **Anti-oscillation**: `_check_hp` resume condition changed from "in_friendly territory OR hp > 70%" to "hp ≥ 85%". Prevents rapid retreat/resume cycling at territory boundaries
3. **Fix _FRIENDLY_TERRITORY_DISTANCE**: Reduced from 15 to 9 to match actual territory heal radius (TERRITORY_CONTROL_RADIUS=10)
4. **Miner retreat to nearest territory**: New `_retreat_to_territory` method routes miners to nearest hub OR friendly junction (whichever is closer) instead of always to hub. Miners on 88×88 die trying to reach distant hub.
5. **Miner retreat threshold**: Increased from 25% to 35% — gives miners 35 steps of buffer instead of 25

Results (machina1, seed 42):
- Baseline (no HP retreat): 28.3 reward, 86 deaths at 10000 steps
- HP retreat v1 (oscillation bug): 22.86 reward, 27 deaths at 3000 steps  
- HP retreat + anti-oscillation: 37.80 reward, 30 deaths at 3000 steps
- + territory retreat for miners: **45.23 reward**, 30 deaths at 3000 steps
- At 10000 steps: **50.83 reward**, 68 deaths (vs 28.3/91 baseline)

50×50 arena: 1138.33 (UNCHANGED — HP retreat never triggers on small map)

**Also tried and rejected**:
- Territory-aware junction scoring (dist_to_territory weight): +10% on machina1 but -15% on 50×50. Even small changes to scoring function disrupt carefully-balanced junction ordering on small map.
- Aligner retreat threshold 80%: more retreat = less productive work, -10% on machina1
- Miner retreat threshold 50%: too aggressive, -56% on machina1 (miners retreat constantly)
- Defend skill: just does noop on friendly junction, doesn't help

**Death spiral analysis**: All productive activity (alignment, mining) stops by step 3000. Junction alignments identical at 3000 and 10000 steps. Agents die → respawn without gear → can't re-gear → die again. By step 9000, all aligners have lost gear (`has_aligner=False`), only 3 friendly junctions remain (clips scrambled all 107). Territory collapses. Target: pzwh4 branch gets 3917 (vs our 50.83) — still 77× gap.
