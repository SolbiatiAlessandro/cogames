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
