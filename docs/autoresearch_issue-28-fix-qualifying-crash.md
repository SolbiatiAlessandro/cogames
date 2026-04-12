# Autoresearch Issue 28: Fix Qualifying Crash (BackoffLimitExceeded)

Branch: `claude/amazing-meitner-rg4mI`

**Issue direction:** Our best offline policy (cross_role, +37% reward) never reaches the competition pool because every qualifying match crashes with `BackoffLimitExceeded`. The qualifying pool is 8-agent self-play, and our policy makes 8 concurrent LLM API calls that overwhelm the container.

**Success criteria:**
- CrossRolePolicy completes 8-agent self-play for 10k steps without crashing
- At least stable enough to pass qualifying (2/2 matches)
- Score >= 3.5 once in competition pool

**Root cause analysis (from code review):**
1. `CrossRolePolicy._plan_skill` has a 3-retry loop with `time.sleep(3*attempt)` — worst case 18s/agent blocking
2. All 8 agents make LLM calls (no `scripted_miners` option like MachinaLLMRolesPolicy)
3. `LLMMinerPlannerClient._complete_openrouter` creates a new `httpx.Client` per call (no pooling)
4. With 8 agents × 3 retries × (10s timeout + 9s sleep) = 456s per planning cycle in worst case

**Planned fixes:**
- Fix A: Add `scripted_miners` option to CrossRolePolicy (proven in MachinaLLMRolesPolicy)
- Fix B: Remove retry-with-sleep loop, use single-attempt + graceful scripted fallback
- Fix C: Add HTTP connection pooling to LLMMinerPlannerClient

---

## 2026-04-12T00:00:00Z: autoresearch starting, my plan is to...

Starting issue #28. Root cause: CrossRolePolicy crashes in 8-agent qualifying because all agents make LLM API calls with aggressive retry+sleep. Plan is to:
1. Run baseline 8-agent 1000-step to reproduce the crash/slowness
2. Implement scripted_miners for CrossRolePolicy
3. Remove retry-with-sleep loop in _plan_skill
4. Add HTTP connection pooling
5. Test at 10k steps to confirm stability

---
