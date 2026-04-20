# Issue #43: v34 Regression — WebSocket 1011 Error

## 2026-04-20T00:00: autoresearch starting

**Plan**: Diagnose why v34 crashes (WebSocket 1011) while v33 works fine (score 11.84). Fix the root cause and upload a working v35.

## 2026-04-20T00:01: Root cause analysis

**Root cause identified**: v34 was uploaded from the repo at commit `b9ffa75` (session 11), which still had bare `import httpx` in `llm_miner_policy.py` line 11. The tournament server doesn't have httpx installed, so the import crashes during policy initialization.

v22-v33 were uploaded from branch `claude/amazing-meitner-ccN7G` which had the httpx fix applied to the bundle. v34 was uploaded from a different branch/commit without the fix.

The fix (try/except ImportError) was applied to the main branch in commit `da4a0ed` (session 12). Current codebase has the fix.

## 2026-04-20T05:28: baseline result

3-agent 500-step baseline: per-agent reward 0.32 (total 0.97). All agents survive.
8-agent 500-step baseline: per-agent reward 0.34 (total 2.71). All 8 agents survive. 4 aligners + 4 miners. 520 element deposits. 10 junctions aligned. No crashes.

## 2026-04-20T05:31: v35 uploaded

Uploaded `lessandro-scripted-v35:v1` to beta-cvc qualifying pool.
Bundle: 77 KB, 23 files. Same code as v33 + httpx try/except fix in repo.
Policy version ID: dca8e469-e21a-419e-8e50-e18d25e12a33

## Root cause summary

The v34 regression was caused by uploading from the repo's main branch (commit `b9ffa75`) which still had `import httpx` at module level in `llm_miner_policy.py`. The tournament server lacks httpx, causing an ImportError during policy initialization -> WebSocket 1011 error.

v22-v33 all worked because they were uploaded from branch `claude/amazing-meitner-ccN7G` which had the fix applied directly to the bundle before zipping. v34 was uploaded from the unfixed repo.

The fix (try/except ImportError with httpx=None fallback) was applied to the repo in commit `da4a0ed` (session 12). v35 was uploaded from this fixed code.

## Next: transition to #36 (agent mortality)

With v35 uploaded, the v34 regression is resolved. Now transitioning to the highest-leverage remaining issue: agent mortality (#36). Our agents survive only 15-31% of 10k-step episodes. This is the #1 online bottleneck.
