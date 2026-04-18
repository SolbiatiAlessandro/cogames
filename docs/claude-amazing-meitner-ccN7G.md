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
