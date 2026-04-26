# Experiment Log: claude/amazing-meitner-MIW4I

Issue: #48 — Cherry-pick critical #38 fixes: miner/scout crash-prevention wrappers

## 2026-04-26T00:00: autoresearch starting

**Plan**: Issue #48 asks to cherry-pick crash-prevention try/except wrappers from branch dtLLg and validate offline. On inspection, the wrappers are already present in the current code:
- `llm_miner_policy.py` lines 360-365: try/except around `_planner.complete(prompt)` in `_plan_skill`
- `llm_miner_policy.py` lines 476-480: try/except around `_step_impl` in `step_with_state`
- `scout_agent.py` lines 335-339: try/except around `_step_impl` in `step_with_state`

All match the aligner pattern at `machina_llm_roles_policy.py` lines 219-224.

**My task**: Validate offline at 8 agents (5A+3M) for 3000 and 10000 steps to confirm no regression. Then look for further reward improvements.

## 2026-04-26T00:01: starting to run baseline

Baseline result with HEAD (cbbc1e9): **826.4** total reward at 3k/seed42.
This is -13% vs previous best (949.1 from commit 3a92ad2).

**Root cause found**: `_JUNCTION_ALIGN_DISTANCE` was changed from 15 to 20 in the session 16 merge commit.
Reverting to 15 immediately restores 949.1 (exact match).

## 2026-04-26T00:15: Experiment 1 — Junction distance fix + dynamic role assignment

### Changes:
1. **Fix junction distance regression**: `_JUNCTION_ALIGN_DISTANCE` 20→15 (+14.8% reward)
2. **Dynamic proportional role assignment**: Replaced static `aligner_ids={0,1,2,3,4}` with counter-based allocation. First N agents become aligners, rest miners. Works with any agent IDs.
3. **Hub side diversification**: Uses `aligner_index % 4` instead of `agent_id % 4` for hub approach

### Failed experiments along the way:
- Miner stale retargeting (skip explore, go directly to next extractor): WORSE (815 vs 949) — miners need explore to find fresh areas
- return_load=30: WORSE (607) — too much hub congestion from frequent deposits
- return_load=50: WORSE (163) — miners never reach threshold
- 6A+2M: WORSE (875) — fewer miners = fewer hearts
- Hub align distance 20: WORSE (736) — too few alignable junctions
- Hub align distance 30: WORSE (725) — too much travel to far junctions
- Cascade weight 1.0: WORSE (818) — aligners stuck near hub
- Cascade weight 0.5: WORSE (904) — less directional
- Cascade-aware junction targeting: WORSE (823) — far cascade junctions not worth travel
- Move cooldown 4: WORSE (861) — agents retry blocked cells too soon
- Move cooldown 8: WORSE (664) — agents avoid free cells too long

### Results (commit ee6fd4a):
| Seed | Steps | Total Reward | Junctions | Hearts | Status |
|------|-------|-------------|-----------|--------|--------|
| 42   | 3000  | 949.1       | 52        | 56     | keep   |
| 123  | 3000  | 905.7       | 51        | n/a    | keep   |
| 7    | 3000  | 1011.7      | 55        | n/a    | keep   |
| 42   | 10000 | 3917.3      | 52        | 57     | keep   |

All match previous best exactly. The dynamic role assignment preserves offline performance while enabling proper partner robustness online.

## 2026-04-26T00:30: Experiment 2 — Miner navigation shake

### Changes:
1. **Miner navigation shake**: Added same nav shake that aligners have — after 5 consecutive blocked moves, every 3rd step try a random direction. This breaks BFS deadlocks caused by agent congestion near extractors/hub.

### Failed experiments along the way:
- Aligner nav shake threshold 3: WORSE (821) — too aggressive, disrupts normal navigation
- Miner nav shake threshold 3: WORSE (787) — same issue
- Aligner skill timeout *3 (60 steps): WORSE (822) — aligners need 100 steps for distant junctions
- Aligner explore cap *3 (60 steps): WORSE (743) — too much idle explore time
- Aligner explore cap *1 (20 steps): WORSE (777) — not enough explore time
- Move_blocked_cells clear on skill transition: Mixed (973 seed42, 749 seed7) — global clear hurts miners
- Aligner BFS-without-cooldowns: WORSE (811) — cooldowns serve their purpose for aligners
- Directional explore for aligners: WORSE (891) — nearest frontier is usually correct
- Cascade weight 0.0 (travel only): WORSE (812) — hub_dist weight is important
- Cascade weight 0.6: WORSE (890) — slightly worse than 0.7
- Cascade weight 0.8: WORSE (895) — slightly worse than 0.7
- Adaptive cascade weight (1.0 early, 0.7 late): WORSE (740) — early 1.0 too restrictive
- Heart queue max 3: WORSE (919) — too much hub congestion
- Heart queue disabled: WORSE (828) — queue is important
- Heart queue defend fallback: WORSE (766) — explore finds new junctions, defend doesn't
- Miner cooldown 4 (aligner kept at 6): WORSE (905) — miners also need 6
- Move cooldown 5 (global): WORSE (733) — cooldown 6 is critical

### Results:
| Seed | Steps | Baseline | With Change | Delta | Status |
|------|-------|----------|-------------|-------|--------|
| 42   | 3000  | 949.1    | 954.8       | +5.7  | keep   |
| 123  | 3000  | 905.7    | 905.7       | +0.0  | keep   |
| 7    | 3000  | 1011.7   | 1020.6      | +8.9  | keep   |
| 42   | 10000 | 3917.3   | 3923.0      | +5.7  | keep   |

Consistent small improvement (+0.6-0.9% on seed 42 and 7). System is very well-optimized — 17 of 18 parameter/structural changes hurt performance.
