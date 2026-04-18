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
