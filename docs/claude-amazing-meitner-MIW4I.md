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
