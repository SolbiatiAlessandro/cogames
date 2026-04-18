# Experiment Log: Issue #42 - Fix httpx import crash

## Issue
Policy `lessandro-scripted-v21:v1` gets 0 matches on tournament server because `import httpx` at module level in `llm_miner_policy.py` crashes if httpx is not installed on the episode runner.

## 2026-04-18T10:30: autoresearch starting
My plan is to:
1. Run baseline to verify current code works locally
2. Apply try/except fix for httpx import (Option A from issue)
3. Guard all httpx usage so scripted fallback works without httpx
4. Test locally with httpx unavailable to verify crash is fixed
5. Re-upload policy as v22 and submit to beta-cvc tournament
6. Monitor for qualifying matches

## 2026-04-18T17:17: Baseline result
- Per-agent reward: 0.339 at 500 steps, 8 agents, seed 42
- Deposits: C=40, O=35, Ge=33, Si=43 (total ~151)
- aligned.junction.held: 2889
- Hearts withdrawn: 5
- Deaths: 0.12

## 2026-04-18T17:20: Fix applied and tested
**Change**: Wrapped `import httpx` in try/except in `llm_miner_policy.py`:
```python
try:
    import httpx
except ImportError:
    httpx = None
```
Also guarded `_get_http_client()` to raise clear error if httpx is needed but missing.

**Verification**:
1. Import test with httpx blocked: PASS — both `llm_miner_policy` and `machina_llm_roles_policy` import without httpx
2. Post-fix episode: Per-agent reward 0.339 (same as baseline — no regression)
3. Bundle created (254 KB) with fix verified in bundle

## 2026-04-18T17:25: Upload blocked — tournament server 503
Tournament server `api.observatory.softmax-research.net` returning 503 on all endpoints.
Upload retry script running in background. Bundle `submission_v22.zip` is ready.

## 2026-04-18T17:30: Continuing with experiment loop
While server is down, continuing with offline improvements. The httpx fix is committed and pushed to `claude/amazing-meitner-ccN7G`.
Next steps when server comes back:
1. Upload `lessandro-scripted-v22` with fix
2. Monitor for qualifying matches
3. If matches happen, verify score > 0

## 2026-04-18T17:35: Starting new experiment loop - investigating reward gap

Best recorded offline: 8.133 total at 500 steps (4A4M scripted). Our baseline: 2.711.
Possible causes of 3x gap:
- Different mettagrid version (PyPI 0.15.0 vs git 0fe9b54)
- Stuck_threshold tuning (28 was found optimal vs default 20)
- Configuration details (return_load, agent mix)

Hypothesis: stuck_threshold=28 + return_load tuning will significantly improve reward.
Plan: Run sweeps of key parameters.

## 2026-04-18T17:50: UPLOAD SUCCESSFUL!
- **Policy**: `lessandro-scripted-v22:v1`
- **Season**: beta-cvc, qualifying pool
- **Bundle**: 254 KB with httpx fix verified
- **TWO qualifying matches immediately started running!** (7220a14e, a59e1693)
- This confirms the httpx fix works — policy loads on tournament server without crash

## 2026-04-18T17:52: Config sweep results (offline)
At 1000 steps, 3 seeds:
- 4A4M (default): avg 0.795/agent
- 5A3M: avg 0.835/agent (+5%)
- 6A2M: avg 0.860/agent (+8.2%)

At 3000 steps, 3 seeds:
- 4A4M: avg 1.224/agent (high variance: seed 42=1.615 vs seeds 43-44=~1.03)
- 6A2M: avg 1.198/agent (more consistent)

## Replay analysis (500 steps)
- Reward accelerates: 0.0014/step → 0.0083/step (6x improvement over episode)
- Agent A4 stuck 36% of time — worst performer
- Other agents: 9-27% stuck rate
- All agents spread across map (good dispersion)

## 2026-04-18T18:25: Tournament analysis and critical role allocation bug fix

**Tournament results for lessandro-scripted-v22:v1**: Rank 89/111, avg score 6.62.
Top policies score 35-40. Our scores ranged from 0.00 to 48.43 depending on opponent quality.

**Critical bug found**: `n_aligners = min(4, n_agents)` means with 4 or fewer agents (common in tournament), ALL agents become aligners and NONE mine. Matches show 2-agent and 4-agent team sizes where we had 0 miners. This explains the 0.00 and very low scores.

**Fix applied**:
1. Changed `n_aligners = min(4, n_agents)` → `n_aligners = min(4, n_agents // 2)` to ensure at least half agents are miners
2. Changed scripted_miners and scripted_aligners auto mode to always True (LLM API unavailable on tournament server — was wasting time on failed HTTP calls before fallback)

New role allocation:
- 1 agent: 0A 1M
- 2 agents: 1A 1M
- 3 agents: 1A 2M
- 4 agents: 2A 2M
- 6 agents: 3A 3M
- 8 agents: 4A 4M

Hypothesis: This fix alone should dramatically improve tournament scores since we now actually have miners at all team sizes.

## 2026-04-18T18:35: Role allocation fix results

**Also fixed**: Disabled scouts (n_scouts=0 always). With 4 agents, old config gave 2A+1S+1M (only 1 miner!). New config: 2A+2M.

**return_load experiment**: Tried return_load=20 (faster cycling). Result: 8-agent reward dropped 0.339→0.331 (more round trips waste time). Reverted to 40.

**Results with all fixes (return_load=40, no scouts, fixed role allocation)**:
| Config | Per-agent reward | Deposits (C/O/Ge/Si) | Hearts |
|--------|-----------------|----------------------|--------|
| 8A (4A4M) | 0.339 (unchanged) | 49/44/37/40 | 4.95 |
| 4A (2A2M) | 0.405 (+22%) | 52/52/47/52 | 3.60 |
| 2A (1A1M) | 0.224 (was broken) | — | 3.67 |

**Uploaded**: lessandro-scripted-v24:v1 (qualifying)
**Previous**: lessandro-scripted-v23:v1 (qualifying, has role fix but still had scouts+return_load issues)

## 2026-04-18T18:50: stuck_threshold sweep and tournament results

**Tournament update**: v23 already moved from rank 89 → 76, score 6.62 → 8.72 (+32%)!

**stuck_threshold sweep** (5 seeds, 8 agents, 500 steps):
| Threshold | Avg reward/agent | vs baseline |
|-----------|-----------------|-------------|
| 20 (old)  | 0.334           | baseline    |
| 12        | 0.364           | +9.0%       |
| 8         | 0.359           | +7.5%       |

Optimal: stuck_threshold=12. Faster stuck detection means less wasted time, but too aggressive (8) causes thrashing.

**Uploaded**: lessandro-scripted-v25:v1 with stuck_threshold=12 + all prior fixes
