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
