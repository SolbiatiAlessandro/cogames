# Experiment Log: claude/amazing-meitner-095mA (Issue #68)

## Issue: P0 — contamination-v64 crashes 100% online

**2026-05-09T12:00:00Z**: Autoresearch starting. My plan is to investigate and fix the P0 crash in contamination-v64 that fails 100% of online matches. The director confirmed imports pass — it's a runtime crash. Strategy:
1. Read the diff between v52 (working) and current code
2. Run baseline locally to confirm it works
3. Follow bisect strategy: upload v52 + minimal changes incrementally
4. Find and fix the crash source
5. Upload working policy with contamination improvements

---

**2026-05-09T13:00:00Z**: Investigation complete. Root cause identified.

### Root cause: Partial bundle shadowing (same bug as issue #28)

All 8 matches (4 beta-cvc + 4 beta-teams-tiny-fixed) failed with `received 1011 (internal error)`, `episode_id=None`, and empty policy logs. The crash happens before ANY game code runs — at the import/initialization level.

**The policy code itself is NOT the problem.** Both `LLMMinerPolicyImpl.step_with_state` and `LLMAlignerPolicyImpl.step_with_state` have try/except guards that catch ALL exceptions and return noop. The contamination code changes cannot cause a WebSocket 1011 crash.

**The actual bug:** When contamination-v64:v2 was submitted with `--include-files` pointing to only the modified policy files, the bundle mechanism (`_collect_ancestor_init_files`) also included `src/cogames/__init__.py` and `src/cogames/policy/__init__.py`. These shadow the server's installed `cogames` package with a partial one. When `machina_llm_roles_policy.py` tries to import other modules like `cogames.policy.starter_agent`, they're not in the bundle -> `ModuleNotFoundError` -> crash before any gameplay.

This is exactly the same bug documented in issue #28 (April 2026), where the fix was "v8 approach: include ALL `.py` files from the full `cogames/` package."

### Fix applied

Created `scripts/upload_full_bundle.py` — builds a zip bundle with ALL 21 `.py` files from `src/cogames/policy/` plus the parent `cogames/__init__.py`. This provides a complete `cogames.policy` namespace that correctly shadows the server's installed version.

Uploaded:
- `lessandro-contamination-v64:v3` -> beta-cvc qualifying pool
- `lessandro-contamination-v64:v4` -> beta-teams-tiny-fixed entry pool

Waiting for match results to confirm the fix works.

### Files changed (v52 -> current, the contamination fix)
Only 3 policy files changed:
- `aligner_agent.py`: `_JUNCTION_ALIGN_DISTANCE` 20->25, added contamination fields to AlignerState
- `llm_miner_policy.py`: contamination detection in `_maybe_finish_skill`, faster gear_up timeout
- `llm_skills.py`: 3 new MinerSkillState fields, `_select_miner_station` method, contamination avoidance in BFS/explore/wander

All changes are the +15.2% contamination avoidance fix from the EnIvJ branch (10-seed validated offline).

---

**2026-05-09T18:00:00Z**: Starting issue #67 experiments while waiting for #68 match results.

### Experiment 1: Reduce heart wait time at hub (issue #67)

**Hypothesis**: Aligners spend too long waiting at the hub for hearts. Reducing the max heart wait from 6 to 3 ticks and max hearts per trip from 4 to 3 will speed up the aligner cycle, increasing hearts withdrawn per 3000 steps.

**Changes**:
- `machina_llm_roles_policy.py` line 368: `heart_count < 4` -> `heart_count < 3`
- `machina_llm_roles_policy.py` line 368: `no_progress_on_target_steps < 6` -> `no_progress_on_target_steps < 3`

Testing online since local environment has dependency issues.

---

**2026-05-09T18:30:00Z**: CRASH FIX CONFIRMED!

### contamination-v64:v3 — first match completed successfully

- **Score: 44.10** (qualifying match, solo 8 agents)
- Episode ID: 32478f4d
- Replay: https://softmax-public.s3.amazonaws.com/replays/39034bb6-3bc4-4abf-b85b-5dace1ef3f74.json.z
- All 8 agent logs available (policy_agent_0.txt through policy_agent_7.txt)

This confirms the root cause was the partial bundle shadowing. The full-bundle upload script (`scripts/upload_full_bundle.py`) fixes the issue.

Note: 44.10 is a qualifying score (solo), not a competitive CvC score. v52's competitive average is 36.45. The qualifying score is higher because there's no opponent. Once v3 passes qualifying (needs 2 matches), it will get competitive CvC matches against other policies.

### Aligner throughput experiments uploaded (issue #67)

While waiting for the crash fix, uploaded 3 variants:
- `aligner-opt-v1:v1`: hearts<3 + wait<3 ticks (4A+4M, JUNCTION=25)
- `aligner-opt-v2:v1`: hearts<3 + wait<3 ticks + JUNCTION_DIST=30 (4A+4M)
- `aligner-opt-5a3m:v1`: same as v2 but 5A+3M allocation

All 3 are currently running qualifying matches on beta-cvc.

