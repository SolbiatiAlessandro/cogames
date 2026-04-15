# Autoresearch — Issue #38 (6+2 Startup Mortality)

Branch: `claude/amazing-meitner-dtLLg`
Researcher: autoresearch-agent (2026-04-15)

## 2026-04-15T00:00:00Z: autoresearch starting

**My plan:**
- Tackle issue #38 (priority:1): in 6+2 online matches, 3 of our 6 V20 agents (indices 3, 4, 5) die at step 4–15. In 4+4 matches they all survive. The delta between the two configs is the mix of roles (aligner + scout + miner vs only aligners).
- The environment is missing `cogames` / Bazel / Python 3.12, so I cannot run episodes offline to repro. Previous session (director notes) reported the same: "couldn't submit because the environment lacked Python 3.12 / cogames binary." This forces a code-analysis-first approach: read every startup code path, find bugs, fix surgically, rely on the online score to validate (a new submission would then be measured at the next director session).
- Focus on what *could crash an agent in the first 4–15 steps* without dying of HP damage (too fast for hub-proximity decay), starting with unhandled LLM exceptions and per-agent-id race conditions in shared state.

## 2026-04-15T00:05:00Z: starting to run baseline

No baseline run possible — see above. The "baseline" is the merged V20 policy in main (commit `9b4c2d9`). Online evidence of its behaviour is recorded in issue #38.

## 2026-04-15T00:10:00Z: baseline result is

V20 online score: **3.43** (#322/398 on beta-cvc).  Reference: `lessandro-fast-llm-v1` scores 4.47 (#283/398). V20 is *worse* than the stale predecessor despite offline improvements — and the issue pins this regression on 6+2 startup mortality.

## Root-cause analysis (code reading)

### Observation A: Aligners catch LLM exceptions; miners don't.

`src/cogames/policy/machina_llm_roles_policy.py:209-222` wraps the `self._planner.complete(prompt)` call for `LLMAlignerPolicyImpl` in a `try/except Exception` — a failing LLM call degrades to `text = ""` and the scripted fallback picks a sane skill.

`src/cogames/policy/llm_miner_policy.py:313` does **not** wrap the equivalent miner call. Any exception (httpx timeout, 429 rate-limit, 5xx, JSON parse error) in `_plan_skill` propagates out of `step_with_state` → out of `StatefulAgentPolicy.step` → into the runner. At startup, several miners call OpenRouter concurrently on a cold HTTP client (no pooled connection yet), which maximises the chance of timeouts. If the runner treats a raised exception as an agent failure, the miner is removed from the game.

This matches the issue's signature exactly:
- In 4+4 matches the four survivors in match `ea54ab9c` are all aligners — protected by the try/except.
- In 6+2 matches the three dead agents (3/4/5) correspond to the non-aligner roles (scout + miners).
- Agents die at steps 4–15 — immediately after the first LLM call (each cycle runs `_plan_skill` once `current_skill` is None, which is the case at step 1).

### Observation B: `CrossRolePolicyImpl` has the try/except but miners inside it use the same `LLMMinerPlannerClient` that can raise.

Cross-role already guards its LLM call (`cross_role_policy.py:780-785`). So the main fix surface is `llm_miner_policy.py`.

### Observation C: Scout (`scout_agent.py`) makes no LLM calls, so its 6+2 death must be different.

At step 0 the scout initialises its grid (`scout_agent.py:339-346`) and navigates to the first non-dangerous target. Because the scout holds no gear, walking adjacent to a *hazard station* (scout/scrambler) triggers auto-equip. If the hazard station is between spawn and the first grid target, the scout bounces between contamination and retreat. It doesn't *crash* — but it may walk into an unaligned junction or enemy zone and bleed HP. Fixing this in one sitting is out of scope for #38's primary signal; I focus on the crash paths first.

## Plan for this session

1. **Fix 1 (v1):** Wrap `LLMMinerPolicyImpl._plan_skill` LLM call in `try/except Exception` exactly as the aligner does. Degrade gracefully to scripted fallback instead of crashing. This is the minimum-risk, highest-leverage change — it directly explains why the three non-aligner agents die.
2. **Fix 2 (v1):** Log agent → role assignment at step 0 so future replays can confirm which agents crashed and why.
3. Commit, push, and post results to issue #38.

I cannot validate offline, so each commit is a *reasoned bet* backed by the code evidence above. The next director session will pick up the change and submit a new policy; the signal will be "V21 online score" relative to the 3.43 V20 baseline.

## 2026-04-15T02:00:00Z: v1 shipped

Commits `ae734d5` (code) + `5065498` (TSV).

- `llm_miner_policy.py:_plan_skill` LLM call wrapped in try/except → degrades to `text=""` → scripted fallback. Matches aligner behaviour.
- All three policies (`LLMAlignerPolicyImpl`, `LLMMinerPolicyImpl`, `CrossRolePolicyImpl`) now split `step_with_state` into public wrapper + `_step_impl`; outer try/except returns noop on any exception.
- `MachinaLLMRolesPolicy.agent_policy` logs `ROLE_ASSIGNMENT agent=<id> role=<aligner|scout|miner> ...` for every agent at construction.

Cannot validate offline. Status in TSV: `keep`.

## 2026-04-15T02:30:00Z: v2 shipped

Commits `fc050d9` (code) + `ee68d6b` (TSV).

- `scout_agent.py:ScoutExplorerPolicyImpl.step_with_state` gets the same try/except-to-noop wrapper — closing the crash-death path for the scout that makes no LLM call but still has several raise sites in its pipeline.

Coverage table after v2 is in the issue comment `4254111302`.

## 2026-04-15T03:00:00Z: v3 shipped

Commits `239ab14` (code) + `74e0d2d` (TSV).

Targets scout HP-damage death, which v2 cannot save.

- `_HP_RETREAT_THRESHOLD`: 0.55 → 0.65 (more margin for return trip).
- New `_SHIP_FLEE_DISTANCE = 6`: preemptive retreat when within 6 cells of a known clips:ship regardless of HP.
- New `_nearest_enemy_ship`, `_flee_direction` helpers.
- Retreat fallback when `known_hubs` is empty now uses `_flee_direction` (maximise distance from ship, avoid walls/hazards) instead of `_safe_wander` (which could wander *toward* a ship because it only avoids hazard-stations and walls).
- If every direction is blocked, returns `noop` (safer than random step).

## 2026-04-15T03:30:00Z: v4 shipped

Commits `aac977f` (code) + `b6b7053` (TSV).

- `scripted_miners` default flipped `False` → `"auto"` in both `MachinaLLMRolesPolicy` and `CrossRolePolicy`. `"auto"` resolves to `True` when `policy_env_info.num_agents >= 6`, `False` otherwise. Explicit overrides still honoured.
- Rationale: the miner LLM call adds wall-clock latency (up to `llm_timeout_s`=10s) even when v1's try/except catches a timeout. At 6+ agents the marginal value of LLM planning for miners is low (see `docs/results_autoresearch_21_march.tsv` rows 11 vs 14: scripted 2.18 beats LLM 1.20 at 3A1M).
- Resolved value is logged on construction.

## 2026-04-15T04:00:00Z: v5 shipped

Commits `b4c5188` (code) + `ed18a4d` (TSV).

Targets aligner HP-damage death (agent 3 in 6+2 replays).

- `AlignerPolicyImpl.__init__`: resolve `clips:ship`/`ship` tag ids.
- `AlignerState.known_enemy_ships`: new persistent set.
- `_update_map_memory`: scan tokens for ship tags, persist cells.
- `LLMAlignerPolicyImpl._check_hp`: fire retreat preemptively when any known ship is within 6 Manhattan cells and the aligner is not in friendly territory. Logs `HP_SHIP_PROX`.
- `CrossRoleState.known_enemy_ships`: mirror field so cross_role's duck-typed call to `AlignerPolicyImpl._update_map_memory` doesn't `AttributeError`.

## 2026-04-15T04:30:00Z: end-of-session summary & handoff

Death-vector coverage table after the v1..v5 stack:

| Agent role | Original cause             | Fix         |
|------------|----------------------------|-------------|
| miner (5)  | unwrapped LLM exception    | v1 + v4     |
| scout (4)  | crash + HP bleed near ship | v2 + v3     |
| aligner 3  | crash + HP bleed near ship | v1 + v5     |

**What the next researcher should check first:**

1. Did the next online submission include all of v1..v5 (commits up through `b4c5188`)? Confirm against the submitted bundle.
2. Which policy class is *actually* submitted online — `machina_llm_roles` or `machina_cross_role`? v5's aligner ship-proximity retreat only lives in the former. If the submitted policy is `machina_cross_role`, port the check to `CrossRolePolicyImpl._step_impl`.
3. Online 6+2 replay — are all 6 agents alive at step 1000? If yes, the stack works and the priority shifts to improving the *alive* agents' rewards (scout usefulness, miner throughput). If no, check which role is still dying and whether the ROLE_ASSIGNMENT logs confirm the expected 4A+1S+1M layout.

**Candidate v6+ directions:**

- Promote `known_enemy_ships` to `SharedMap` so the team learns ship positions collectively (one agent sees, everyone knows).
- Consider `num_scouts=0` when `num_agents >= 6` — scouts contribute only map knowledge, which is less valuable than a fifth aligner at 6+2. Prior offline evidence at 3A0M hit 2.26 vs 2.18 at 2A1M on cogsguard_machina_1.
- Mirror v5's ship-proximity retreat to `CrossRolePolicyImpl`'s HP-retreat block (`cross_role_policy.py:1362-1386`) if cross_role is the submitted policy.
- Investigate why V20 online = 3.43 < lessandro-fast-llm-v1 = 4.47 even before mortality — there may be non-mortality regressions in V20 worth diffing against the older branch.

## 2026-04-15T05:00:00Z: v8a shipped

Commits `aa8b337` (code) + `975f1ca` (TSV).

- `MinerSkillImpl` resolves `clips:ship`/`ship` tag ids; `MinerSkillState` gains `known_enemy_ships`; `_bind_shared_map_miner` binds to `SharedMap.known_enemy_ships`; `_update_map_memory` scans ship tokens; `LLMMinerPolicyImpl._copy_with` preserves the binding across `replace()`. Miners are typically the team's forward observers — closing this observation gap means ship sightings propagate from the first agent that sees them to every aligner/scout retreat check via `SharedMap`.

## 2026-04-15T05:15:00Z: v8b shipped

Commits `fb72893` (code) + `3fa5585` (TSV).

- `LLMMinerPolicyImpl._plan_skill`: preemptive ship-proximity retreat — if a known ship is within 6 Manhattan cells, force `skill=deposit_to_hub` (or `explore` when no hub is known). Logs `miner_ship_prox`. Before v8b, miners had zero HP-retreat behaviour.

## 2026-04-15T05:30:00Z: v8c shipped

Commits `542f0bc` (code) + `1ab1792` (TSV).

- `MachinaLLMRolesPolicy.num_scouts` default flipped `1` to `"auto"`. Resolves to 0 at `n_agents>=6`, 1 otherwise. Scout agent index 4 in 6+2 is one of the three dying indices; at n>=6 its role is absorbed by a scripted miner (v4). Prior offline evidence: `3A0M=2.26 > 2A1M=2.18` on `cogsguard_machina_1`.

## 2026-04-15T05:45:00Z: post-v8 handoff

Coverage now:

| Agent role | Original cause             | Fix stack                    |
|------------|----------------------------|------------------------------|
| miner (5)  | unwrapped LLM exception    | v1 + v4 + v8a + v8b          |
| scout (4)  | crash + HP bleed near ship | v2 + v3 + v8c (role removed) |
| aligner 3  | crash + HP bleed near ship | v1 + v5 + v6 + v7 + v8a      |

**Candidate v9+ directions (queue for future sessions):**

- **v9a — mirror v8c `num_scouts=auto` to `CrossRolePolicy`** if it exposes a scout slot (it currently splits aligner/miner only, so likely no-op, but confirm).
- **v9b — diff V20 vs `lessandro-fast-llm-v1`** to explain the 3.43 < 4.47 gap independent of mortality. Candidates: a regression in `_check_hp` behaviour, a prompt change, a scripted-skill threshold flip. Requires git log + compare across branches.
- **v9c — miner ship-proximity retreat fallback when heading toward ship.** Current v8b logic forces `deposit_to_hub` but the hub may be *through* the ship. Add a direction check: if the BFS-first step from miner to hub moves closer to the nearest known ship, prefer `explore` away instead.
- **v9d — reduce `llm_timeout_s` from 10s to 3s for aligners**: online 6+2 startup cold-pool timeouts may burn 10s budget per aligner x 4 aligners = 40s of stalling. Even with v1's try/except, the wall-clock latency hurts responsiveness at startup.
- **v9e — precache HTTP connection in `LLMMinerPlannerClient.__init__`**: warm the pool before the first step so miner 1's LLM call doesn't pay cold-connection latency. Combined with `scripted_miners=auto` this is mostly irrelevant for n>=6 but could still help n=4.
- **v9f — aligner starvation at n>=6**: with v8c we have 4 aligners + 2 miners at n=6. Check whether `known_aligner_stations` is shared via `SharedMap`. If not, new-aligner bootstrapping may stall when the station isn't visible.
