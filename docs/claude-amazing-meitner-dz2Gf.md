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
