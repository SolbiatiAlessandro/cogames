# Director Notes
_Written: 2026-04-16 (Session 9)_

## What I observed

### Online performance (V20 submission, 20+ matches)
- **V20 online score: 3.28 (#340/405)** — WORSE than old fast-llm-v1 (4.41, #291/405)
- Root cause confirmed: **6+2 startup mortality** — agents 3-5 die at step 4-15 in 6-agent matches
- 6+2 matches (we get 6 agents): avg score ~1.8 — catastrophic
- 2+6 matches (we get 2 agents): avg score ~7.0 — fine
- 4+4 matches: avg score ~5.7 — mixed
- Top-1 dinky:v27 at 27.31 (gap: 8.3x). 405 total entries (up from 363 in session 7)

### Branch review
1. **`claude/amazing-meitner-MGrvP`** (issue #38): **MERGED**. 12 experiments, 10-seed validation. Key breakthrough: scripted aligners at 6+ agents = 196x reward improvement (0.03 → 8.133). Also: heart queue management, junction coordination, frontier explore.
2. **`claude/amazing-meitner-dtLLg`** (issue #38): NOT merged. Code-analysis only (no offline validation) — 8 versions of crash/HP fixes. Largely superseded by MGrvP. Ship-proximity retreat code (v3/v5/v6) is the only novel addition not in MGrvP.
3. **`autoresearch/issue-37-submit-v20-8agent`** (issue #37): **MERGED**. Miner LLM exception handler + 10k validation (1.743/agent). Conflict in llm_miner_policy.py resolved (both branches added same try/except).
4. Other branches (30+ remote): no new activity.

### Could NOT run replays
Environment lacks Bazel for building mettagrid. Replay-based validation was not possible this session.

## Current bottleneck
**NEED NEW ONLINE SUBMISSION.** The merged MGrvP code fixes all identified 6+2 mortality issues (scripted aligners/miners, 0 scouts, defensive wrappers). Offline: 8.133 total reward at 500 steps (10-seed). But the online submission is still the old V20 code (3.28). Issue #39 created for this.

After submission, the **mining throughput gap** is the next frontier: we deposit ~500 elements/10k vs dinky's ~14,000 (28x gap). This limits hearts to ~15/episode vs ~500. Issue #40 created.

## What I expected to happen vs. what I found
Session 8 asked: "Did #37 submit successfully?" — YES, it did. V20 was uploaded as `lessandro-v20-robust-llm-v1:v1`.

Session 8 predicted V20 online score ≥5.0. **WRONG** — actual: 3.28, worse than old policy. The 6+2 startup mortality was the unexpected failure mode. This was never caught offline because all V20 experiments used 3 agents.

Session 8 expected the researcher to validate 8-agent config with V20. This happened on two branches: issue-37 (baseline + 10k) and MGrvP (mortality fix + scripted aligners). MGrvP found the breakthrough: LLM calls are the problem, not the policy logic.

## Issues updated this session
- **#38**: Comment with merge details. Label priority:1→priority:2 (code merged, awaiting submission).
- **#25**: CLOSED as completed — superseded by MGrvP (8.133 vs 0.825/agent plateau).
- **#30**: Comment noting MGrvP addresses core concerns. Label priority:2→priority:3.
- **#39**: CREATED (priority:1) — submit merged MGrvP policy to beta-cvc.
- **#40**: CREATED (priority:2, blocked by #39) — mining throughput gap (28x below dinky).
- **#31, #36, #17, #10, #19, #20, #11**: Moved to priority:3 (lower leverage).

## Priority stack for OpenClaw
```
priority:1  #39  Submit MGrvP policy  <- SPAWN NEXT (highest leverage)
priority:2  #38  6+2 startup mortality (code merged, needs online confirmation)
priority:2  #40  Mining throughput gap (blocked by #39)
priority:2  #24  Balanced Mining Strategy (overlaps #40)
priority:2  #27  Andre Von Huck suggestions
priority:2  #26  shweta policy
priority:3  #32  Partner robustness | #36 Mortality | #30 Self-play
priority:3  #31 change_vibe | #12 Gear | #10 Tuning | #11 Active Inference
priority:3  #17 Skill Validation | #19 LLM Code Gen | #20 Spatial Partitioning
priority:3  #22 Social Influence | #23 Meta-Learning | #21 Intrinsic Motivation
```

## Open questions for next director

1. **Did #39 submit successfully?** Check `cogames submissions --season beta-cvc` for a `lessandro-scripted-v21` entry. If yes, check online score after 24h. Target: ≥6.0 (from current 3.28).

2. **6+2 survival after MGrvP**: The scripted aligners/miners at 6+ agents should eliminate all 3 death vectors (LLM crash, LLM contention, scout fragility). But ship-proximity retreat (dtLLg v3/v5/v6) is NOT included — if HP-death persists online, merge those fixes from dtLLg.

3. **3000-step HP decay**: MGrvP's reward DROPS from 7.248 at 1k to 3.72 at 3k. This means agents are dying from HP drain at longer episodes. Online matches are 10k. The mining throughput gap (#40) likely limits heart production → limits survival.

4. **"Just use A* and hash tables" (Andre Von Huck, #27)**: dinky's 27.31 score uses NO LLM calls, NO ML. Our scripted aligners are a step in this direction — can we make a fully scripted policy that matches/beats the LLM version? MGrvP showed scripted is 196x better than LLM at 6+ agents. Can we extend this to 3-agent as well?

5. **Clean up old branches**: 30+ remote branches. After confirming #39 succeeds, delete merged branches: amazing-meitner-MGrvP, amazing-meitner-JWpsV, amazing-meitner-ahBE5, amazing-meitner-cUcXZ, autoresearch-priority-issue-dAc9K, autoresearch/issue-37-submit-v20-8agent.

6. **Partner robustness (#32)**: Our score still depends heavily on the partner. In 2+6 matches (2 agents of ours), we score ~7.0 but the partner contributes most of that. Can we build a self-sufficient 2-agent carry policy?
