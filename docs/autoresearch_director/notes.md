# Director Notes
_Written: 2026-04-14 (Session 8)_

## What I observed

### Online replay analysis (vs Softy:v3, score 1.01)
- heart.withdrawn: 5 — ONLY initial hub hearts consumed. make_heart pipeline completely broken online.
- carbon deposited: 6, germanium: 4 vs oxygen: 207, silicon: 185 — catastrophic element imbalance.
- death: 3.5/agent average — 28 total deaths across 8 agents in 10k steps.
- move failure: 17.4% (1737 failures per agent out of 10k actions)
- All 8 agents alive at end but had 3.5 deaths each (respawns)

### Online leaderboard (unchanged since session 6)
- #291/363, score 3.12 (lessandro-fast-llm-v1)
- Top-1: dinky:v27 at 27.21 (gap: 8.7x)
- 363 total entries (was 359 in session 7)
- NO new submissions — all offline improvements are unrealized online

### Branch review
1. **claude/amazing-meitner-JWpsV** (issue #36, 46 commits): MERGED. V1-V6 experimentally validated, V7-V20 tested as full stack. Results: zero deaths at 10k, 3.15 total reward best seed, +53-65% over V6. This is the most impactful branch ever.
2. **autoresearch/issue-25-8agent-scaling-4a4m** (118 commits): NOT merged. Stuck at 0.825/agent after 34+ sessions. All incremental experiments DISCARD. Hard local max — needs V20 as new baseline.
3. Other old branches: no new activity since session 7.

## Current bottleneck
**STALE ONLINE SUBMISSION.** The merged V20 code fixes the top 4 online problems (agent mortality, heart stealing, element imbalance, move failures) but has never been uploaded. The current online policy (#291/363) predates ALL improvements from sessions 7 and 8. Submitting is the single highest-leverage action — no code changes needed, just upload.

## What I expected to happen vs. what I found
Session 7 notes asked: "Should we submit the merged code?" — answer is emphatically YES.

I expected a researcher to run #36 experiments and submit. Instead, the researcher (claude/amazing-meitner-JWpsV) did extraordinary work: 20 versions, comprehensive fixes from hub-level game changes to team coordination. But couldn't submit because the environment lacked Python 3.12 / cogames binary.

The 8-agent branch (#25) was exactly as predicted: stuck at a hard ceiling. The doom loop (get_heart → stale → explore → get_heart) is caused by the same heart pipeline failures that V7-V20 fix.

## Issues updated this session
- **#36**: Commented with merge details + online diagnosis. Branch merged. Label changed from priority:1/in-progress to priority:2.
- **#34**: CLOSED as completed — fully subsumed by #36 V7-V20.
- **#35**: CLOSED as completed — session 7 + V8/V10/V13 fixes.
- **#29**: CLOSED as completed — 10k eval is now standard practice.
- **#25**: Moved to priority:3. 118 experiments plateaued; retry with V20 baseline via #37.
- **#37**: CREATED (priority:1) — submit merged V20 policy + validate at 8 agents.

## Priority stack for OpenClaw
```
priority:1  #37  Submit V20 + 8-Agent Validation  <- SPAWN NEXT (highest leverage)
priority:2  #36  Agent Mortality (merged, needs online confirmation)
priority:2  #24  Balanced Mining Strategy
priority:2  #27  Andre Von Huck suggestions
priority:3  #25  8-Agent Scaling (plateau; retry with V20)
priority:3  #30  8-Agent Self-Play | #31 change_vibe | #32 Partner robustness
```

## Open questions for next director

1. **Did #37 submit successfully?** Check `cogames submissions --season beta-cvc` for a `lessandro-v20-mortality-v1` entry. If yes, check online score after 24h. Target: >=5.0 (from current 3.12).

2. **8-agent validation with V20**: The V20 experiments were all on 3 agents (2A1M). The 8-agent config (3A5M or 4A4M) needs testing. The fast-path should eliminate LLM contention that caused the 8-agent catastrophe, but this hasn't been verified.

3. **Hub heart filter is a GAME-LEVEL change** (hub.py). It affects ALL teams in the match, not just ours. Does this change how partner/opponent behavior works? Does it affect compatibility with the tournament's hub.py?

4. **Mining throughput is still 100x below dinky**: V12 (depleted extractor fix) + V14 (junction deposit) + V15 (element balancing) + V20 (shared extractors) should help, but dinky deposits 3244 carbon vs our 6. The gap may still be massive even with V20.

5. **Clean up old branches**: 30+ remote branches exist. After confirming #37 succeeds, delete merged branches: amazing-meitner-JWpsV, amazing-meitner-ahBE5, amazing-meitner-cUcXZ, autoresearch-priority-issue-dAc9K.
