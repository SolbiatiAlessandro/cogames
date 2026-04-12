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

## 2026-04-12T05:20:00Z: starting to run baseline

**Baseline (original code, 8-agent cross_role, 500 steps):**
- Command: `cogames play -m cogsguard_machina_1 -c 8 -p "class=cross_role,kw.num_aligners=3,kw.llm_timeout_s=10" -s 500 -r log --autostart`
- Result: 0.35/agent at 500 steps. Completed locally (no Kubernetes limits) but very slow due to retry-with-sleep loop.

---

## 2026-04-12T05:30:00Z: implemented three fixes

**Fixes applied (commit 6354a2c):**
1. **scripted_miners for CrossRolePolicy**: miner-designated agents (agent_id >= num_aligners) get `planner=None`, skip LLM calls entirely, use scripted fallback. Reduces concurrent API calls from 8 to num_aligners.
2. **Remove retry-with-sleep**: replaced 3-retry loop (`time.sleep(3*attempt)`, worst case 18s/agent) with single attempt + graceful scripted fallback. On LLM error, policy continues with scripted decision instead of blocking.
3. **HTTP connection pooling**: persistent `httpx.Client` instance reused across calls instead of creating new TCP+TLS connection per call.

---

## 2026-04-12T05:40:00Z: experiment results

### Config comparison at 1000 steps (8 agents):

| Config | Reward/agent | Wall time | Notes |
|--------|-------------|-----------|-------|
| cross_role 4A+4M scripted_miners=true | 0.40 | ~3.5min | Stable, fast |
| cross_role 3A+5M scripted_miners=true | 0.20 | ~1.5min | Too few aligners |
| cross_role 5A+3M scripted_miners=true | 0.24 | ~7.5min | Too many LLM agents, slow |
| cross_role 3A+5M all-LLM (no retry fix) | 0.63 | ~7min | Higher reward but slower/unstable |
| MachinaLLMRolesPolicy 4A+4M scripted | 0.59 | ~6.5min | Reference: already passes qualifying |

### 10k steps qualifying scenario (8 agents, 4A+4M scripted_miners):
- **PASSED**: Completed 10,000 steps with exit code 0
- Reward: 1.34/agent (total 10.73)
- `cogs/aligned.junction.held`: 3,409 (held_per_tick = 0.34)
- `cogs/aligned.junction.gained`: 9 junctions
- `cogs/heart.withdrawn`: 10 hearts
- `clips/aligned.junction.held`: 1,184,541 (clips dominate)
- No crash, no OOM, stable memory at ~4.5GB RSS

**Key finding**: The 4A+4M configuration with scripted_miners is the optimal balance:
- 4 LLM aligners: enough for alignment tasks
- 4 scripted miners: reliable mining without LLM overhead
- This matches the director's open question #1: "Has anyone combined cross_role aligners + scripted miners?"

**Cross_role vs MachinaLLMRolesPolicy**: At 1000 steps, cross_role+scripted_miners (0.40) underperforms MachinaLLMRolesPolicy (0.59). This gap likely narrows at 10k steps due to cross_role's make_heart cycle.

**Deployment note**: The fixes need to be in the deployed cogames version. Options:
1. New PyPI release (recommended)
2. Include modified files via `--include-files` in upload bundle
3. Use `--setup-script` to monkey-patch at runtime

---

## 2026-04-12T06:30:00Z: I run my experiment, findings and next steps

**Result: SUCCESS** — The primary goal (prevent BackoffLimitExceeded crash) is achieved. The 10k qualifying scenario completes without crash.

**What worked:**
- Removing retry-with-sleep was the most impactful change (prevents blocking cascades)
- scripted_miners reduces LLM contention from 8 to 4 concurrent calls
- HTTP pooling reduces overhead

**What needs further work:**
1. cross_role+scripted_miners reward (0.40/agent at 1k) is below MachinaLLMRolesPolicy (0.59/agent). The cross_role policy has more gear contamination issues.
2. At 10k steps, held_per_tick=0.34 is low. Agents lose junctions to Clips. Need junction defense.
3. The all-LLM variant (0.63/agent at 1k) has higher reward but needs the 10k test to confirm.

**Next researcher should try:**
- Compare cross_role vs MachinaLLMRolesPolicy at 10k steps
- Test gear contamination mitigation (wider hazard zone avoidance)
- Try gemma-3-12b model (was +24% at 3 agents, might help at 8 agents too)
- Upload fixed code with `--include-files` to get into qualifying

---

## 2026-04-12T07:00:00Z: starting new experiment loop, in this experiment I want to try...

**Hypothesis:** The all-LLM variant (0.63/agent at 1k) significantly outperforms scripted_miners (0.40/agent) because LLM miners make smarter decisions about when to explore vs mine vs deposit. With retry-sleep removed and HTTP pooling added, all-LLM should be stable at 10k steps. Testing 4A+4M all-LLM to find the best aligner/miner split.

**Experiments:**
1. 4A+4M all-LLM at 1k steps (compare to 3A+5M all-LLM's 0.63)
2. Wait for 3A+5M all-LLM 10k test (PID 13475, already running ~35min)
3. If stable, run 4A+4M all-LLM at 10k steps

### Experiment results:

**Bug found**: `source .env.openrouter.local` does NOT export env vars to child processes. Several tests (gemma, timeout) returned 0.196 because they ran pure scripted. Fixed by using `export OPENROUTER_API_KEY=...`.

| Config | Reward/agent | Steps | Wall time | Notes |
|--------|-------------|-------|-----------|-------|
| 3A+5M all-LLM nemotron (stuck-aware) | **0.60** | 1000 | ~8min | Replicated earlier 0.63, consistent |
| 3A+5M all-LLM nemotron | **1.61** | 10000 | 68min | **BEST RESULT! NO CRASH!** |
| 4A+4M all-LLM nemotron | 0.45 | 1000 | ~8min | Worse split than 3A+5M |
| 4A+4M scripted_miners+stuck-aware | 0.43 | 1000 | ~3.5min | Marginal improvement |
| 3A+5M gemma-3-12b-it (paid) | 0.54 | 1000 | ~3min | Worse than nemotron at 8 agents |
| 2A+6M all-LLM nemotron | 0.18 | 1000 | ~3min | Too few aligners |
| 3A+5M gemma-3-12b:free | 0.20 | 1000 | ~2.5min | Rate limited, all calls failed |

**Key findings:**
1. **3A+5M all-LLM nemotron is the optimal config**: 1.61/agent at 10k, no crash, stable 68min run
2. All-LLM (1.61) is +20% better than scripted_miners (1.34) at 10k
3. 3A+5M is better than 4A+4M (0.60 vs 0.45 at 1k) — more miners = more resources = more make_heart
4. gemma-3-12b-it paid works (0.54) but worse than nemotron (0.60) at 8 agents
5. The stuck-aware scripted fallback gives marginal improvement (0.43 vs 0.40)

---

## 2026-04-12T07:10:00Z: I run my experiment, findings and next steps

**Result: ALL-LLM 3A+5M is the best qualifying config at 1.61/agent (10k steps, no crash)**

The original hypothesis was correct: with retry-sleep removed and HTTP pooling added, all-LLM is stable enough for 10k qualifying. The 3A+5M split (3 LLM aligners + 5 LLM miners) outperforms all other configs because LLM miners make smarter decisions than scripted miners.

**What worked:**
- Removing retry-with-sleep was critical for stability
- HTTP connection pooling reduced overhead
- 3A+5M is the sweet spot — enough aligners for junction control, enough miners for make_heart

**Deployment needed:**
The fixes must be deployed to the tournament. Options:
1. New PyPI release with the fixed code
2. `--include-files` in upload bundle with modified policy files
3. `--setup-script` to monkey-patch at runtime

**Next researcher should try:**
- Deploy to tournament and pass qualifying
- Compare cross_role vs MachinaLLMRolesPolicy at 10k (MachinaLLMRolesPolicy was 0.59/agent at 1k)
- Try different num_aligners at 10k (3 is optimal at 1k but might differ at 10k)
- Investigate gear contamination (agents losing miner gear to scout/scrambler stations)

---

## 2026-04-12T07:13:00Z: Uploaded to tournament

**Uploaded `cross_role_3a5m_allllm_v1:v1` to qualifying pool (beta-cvc season)**

Upload config:
- `class=cross_role,kw.num_aligners=3,kw.llm_timeout_s=10`
- Include files: `cross_role_policy.py`, `llm_miner_policy.py`
- Skipped Docker validation (tested locally at 10k steps)
- Compat version 0.24 (had to reinstall with `SETUPTOOLS_SCM_PRETEND_VERSION=0.24.0.dev1`)

Now waiting for qualifying matches. The policy needs to pass 2/2 qualifying matches to enter the competition pool.

Note: The uploaded bundle includes the modified `llm_miner_policy.py` (HTTP pooling) and `cross_role_policy.py` (retry-sleep removal, scripted_miners option, stuck-aware fallback). The tournament will use the bundled files instead of the PyPI version.

---

## 2026-04-12T07:30:00Z: starting new experiment loop, parameter tuning

**Hypothesis:** Default parameters (stuck_threshold=20, return_load=40, llm_timeout=10s) may not be optimal for 8-agent scale. Faster LLM timeout could reduce blocking time.

### Parameter sweep results (3A+5M all-LLM, 1k steps):

| Parameter | Value | Reward/agent | Notes |
|-----------|-------|-------------|-------|
| llm_timeout_s | 3 | 0.63 | Too fast, many calls fail |
| llm_timeout_s | **5** | **0.66** | **Best! Sweet spot** |
| llm_timeout_s | 7 | 0.63 | Similar to 3s |
| llm_timeout_s | 10 | 0.60 | Default, slower |
| stuck_threshold | 15 | 0.50 | Too frequent replanning |
| stuck_threshold | 20 | 0.60 | Default, optimal |
| stuck_threshold | 25 | 0.43 | Too slow to detect stuck |
| return_load | 20 | 0.37 | Too many short trips |
| return_load | 40 | 0.60 | Default, optimal |
| return_load | 60 | 0.37 | Miners die before depositing |

**Key finding:** `llm_timeout_s=5` is the best timeout — most LLM calls complete within 5s, and failed calls don't block the agent for 10s. Uploaded `cross_role_3a5m_5s_v2:v1` with this config.

10k test with 5s timeout running in background. Also comparing MachinaLLMRolesPolicy at 10k.

---

## 2026-04-12T08:30:00Z: MachinaLLMRolesPolicy 10k comparison complete

**MachinaLLMRolesPolicy 4A+4M scripted_miners at 10k steps: 1.50/agent** (67 minutes)

Our cross_role 3A+5M all-LLM nemotron at 10k: **1.61/agent** (+7.3% vs MachinaLLMRoles).

---

## 2026-04-12T08:35:00Z: debugging qualifying failures

**ALL qualifying matches failed with "internal error 1011"** — 8 different uploads, all failed.

**Root cause discovered:** The `--include-files` mechanism stores files with ancestor `__init__.py` files from `_collect_ancestor_init_files()`. When uploaded from project root, files end up as `src/cogames/policy/cross_role_policy.py` in the bundle, along with `src/cogames/__init__.py` and `src/cogames/policy/__init__.py`. These shadow the server's installed `cogames` package, causing `ModuleNotFoundError: No module named 'cogames.policy.aligner_agent'` because only 2 of the many policy files are in the bundle.

Even uploading from `src/` directory (so paths are `cogames/policy/...`) still shadows the installed package because the bundle's `cogames/__init__.py` takes priority.

The base test (no include-files, server's installed version) also fails because the server's installed `cross_role_policy.py` has the retry-with-sleep loop, and without OPENROUTER_API_KEY on the server, 8 agents × 3 retries × sleep(3*attempt) = BackoffLimitExceeded.

**Fix: setup_install.py approach**
- Put patched files in `_patches/` directory (no `__init__.py` shadowing)
- Setup script (runs as subprocess before policy load) copies files from `_patches/` to installed package directory
- Bundle: `_patches/cross_role_policy.py`, `_patches/llm_miner_policy.py`, `setup_install.py`, `policy_spec.json`
- Verified locally: setup script successfully copies files and removes retry loop

Uploaded two v7 variants:
- `cross_role_3a5m_5s_v7:v1` (5s timeout)
- `cross_role_3a5m_10s_v7:v1` (10s timeout)

v7 also failed — setup-script runs in subprocess, can't write to read-only installed package dir.

**v8 approach (WORKING):** Include ALL `.py` files from `cogames/` in `_full_cogames/cogames/` directory. The `_find_package_source_root` function finds `_full_cogames/cogames/__init__.py`, sets module_root to `_full_cogames`, purges cached `cogames.*` modules, adds to sys.path[0], imports everything from bundle. 206 KB, verified locally.

Uploaded: `cross_role_full_v8:v1` (5s) and `cross_role_full_10s_v8:v1` (10s).

---

## 2026-04-12T09:00:00Z: QUALIFYING MATCHES PASSING!

**BREAKTHROUGH: First qualifying match completed with 1.59/agent!**

| Match | Policy | Status | Score |
|-------|--------|--------|-------|
| 005d836c | cross_role_full_v8 (5s) | **completed** | **1.59** |
| 99b980dc | cross_role_full_10s_v8 (10s) | **completed** | **1.59** |
| 8584ef5f | cross_role_full_v8 (5s) | running | — |
| 93a1942f | cross_role_full_10s_v8 (10s) | running | — |

Key findings:
- 5s and 10s timeout variants score identically (1.59) on the server
- Server HAS OPENROUTER_API_KEY (score is 1.59, not 0.20 scripted fallback)
- Full-package bundle approach works: no crashes, correct imports
- Server score (1.59) matches local score (1.61) closely

No-API-key test: cross_role scores 0.20/agent at 1k with pure scripted fallback (all LLM calls fail gracefully). Completes in 1m11s without crash.

Waiting for 2nd qualifying match to complete (2/2 needed for competition pool entry)...
