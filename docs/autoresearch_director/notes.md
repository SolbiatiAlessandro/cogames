# Director Notes
_Written: 2026-04-15 (Session 9, offline-to-online)_

## Session context

Session 8 closed with: "V20 merged offline, NOT submitted online — submit is highest-leverage action (#37)." That action was executed: `lessandro-v20-robust-llm-v1:v1` was uploaded 2026-04-15T08:37:47 UTC and has completed 20 competition matches.

## Offline observations

- Offline best unchanged: **3.15 total reward, 3-agent V20 stack at 10k steps (seed 44, commit 30e1798)**.
- No new TSV rows since session 8. No new autoresearchers pushed branches since merge of `claude/amazing-meitner-JWpsV`.
- All V20 experiments were at 3 agents. 8-agent behavior of V20 is **untested offline**.

## Online observations

### Leaderboard (beta-cvc, 398 entries, 2026-04-15)

| Rank | Score | Matches | Policy | Submitted |
|------|-------|---------|--------|-----------|
| 283 | 4.47 | 28 | lessandro-fast-llm-v1:v1 | 2026-04-09 |
| 322 | **3.43** | 20 | **lessandro-v20-robust-llm-v1:v1** | 2026-04-15 |
| 339 | 3.03 | 32 | lessandro-machina-paid-v1:v1 | 2026-04-09 |
| 342 | 2.95 | 25 | cross_role_full_v8:v1 | 2026-04-12 |
| 344 | 2.86 | 25 | cross_role_full_10s_v8:v1 | 2026-04-12 |
| 355 | 2.75 | 33 | lessandro-2aligner-llm-v1:v1 | 2026-04-09 |

Top-1: `dinky:v27` = 27.31 (127 matches). Gap 8×.

### V20 online replay analysis (3 matches, full episode 10k steps)

All 8-agent matches. Our policy holds 4 or 6 of 8 slots depending on split.

**Per-agent steps alive (out of 10k):**

| Match | Split | Partner | Our agents survival |
|-------|-------|---------|---------------------|
| `16f76ba2` score 0.79 | 6+2 | shweta-v58 | **6794, 6807, 6960, 7, 8, 4** ← 3 die at step 4–8 |
| `d5416b72` score 1.06 | 6+2 | gamma_v3 | **8495, 8522, 8448, 13, 15, 6** ← 3 die at step 6–15 |
| `ea54ab9c` score 12.11 | 4+4 | scissors_v1_v80 | 3236, 6371, 8071, 9848 ← all 4 alive |

**V20 fixes that DO transfer online (confirmed in the 4+4 match):**
- Element balance: `cogs/{carbon,germanium,oxygen,silicon}.deposited = 795/777/776/770` (vs 6/4/207/185 session 8 baseline)
- Pre-block routing: agent 3 had only **1 failure across 9,847 moves**
- Hub heart filter: `heart.gained = 14.4/agent` (session 8 was stuck at 5 initial-hub hearts)

**V20 fix that does NOT transfer online:**
- Mortality at scale: offline 3-agent V20 had 0 deaths; online 6+2 V20 still loses 3 of 6 agents in first 15 steps.

**Zero `change_vibe_*` actions** on our side (issue #31). Partners scissors/gamma have 60–280/agent. Could be a real bug or a replay-log filter — unresolved.

## Offline→Online gap — quantified

1. Offline best: **3.15 reward total, 3-agent, V20 stack, 10k steps, 0 deaths**.
2. Online best: **rank 283, score 4.47**, `lessandro-fast-llm-v1` (pre-V20 code, 28 matches).
3. V20 online: **rank 322, score 3.43** (20 matches, fresh submit). −23% vs fast-llm.
4. Cause of the gap:
   - **Primary**: 6+2 startup-mortality — 3 of 6 V20 agents die at step 4–15. Invisible offline (only tested at 3 agents). Now filed as **#38**.
   - **Secondary**: partner-dependence (stddev 3.40 on 3.43 mean). With strong partners V20 scores 6–12; with weak partners 0.6–3. Partially unavoidable.
   - **Tertiary**: lack of `change_vibe_*` actions — possibly a red herring (see #31), possibly real.

## Current bottleneck

**#38 — the 6+2 startup-mortality bug.** Until 6 of 6 agents actually reach step 100, every other V20 fix is wasted in 6+2 matches (which are the ones that hurt our average most). This bug is an online-specific symptom that cannot be seen offline with 3-agent eval configs.

## What I expected to happen vs. what I found

Expected: V20 online score rises from 3.12 → ≥ 5.0 (session 8 prediction in #37's success criteria).
Found: V20 online score = 3.43 (regression vs 4.47 fast-llm-v1).

This contradicts the offline signal (V20 fixed mortality, element balance, heart stealing, move failures at 3 agents). The contradiction pinpoints the exact offline→online gap: we never tested at 8 agents, and the 8-agent (specifically 6+2) path has a distinct startup failure mode.

## Issues changed this session

- **#37** (Submit V20) — **CLOSED completed** and moved to priority:3. Submission done; outcome documented.
- **#38** — **CREATED** priority:1. "6+2 startup-mortality: 3 of 6 V20 agents die at step 4-15 in online matches."
- **#36** (Agent mortality) — commented with online transfer table; stays priority:2.
- **#31** (change_vibe zero) — priority:3 → priority:2 (V20 also shows the pattern).
- **#30** (8-agent self-play collapse) — priority:3 → priority:2, linked as same-symptom as #38.
- **#25** (8-agent scaling) — commented: gated on #38; stays priority:3, do NOT launch new autoresearchers here yet.

## Priority stack for next spawn

```
priority:1  #38  6+2 startup-mortality (NEW, highest leverage online)
priority:2  #30  8-agent self-play collapse (likely same bug as #38)
priority:2  #31  change_vibe instrumentation (confirm real vs log artifact)
priority:2  #36  Agent mortality (V20 confirmed partial fix online)
priority:2  #24  Balanced mining | #26 Shweta | #27 Andre
priority:3  #25  8-Agent Scaling (gated on #38)
priority:3  #32  Partner robustness
```

## Submission decision this session

**No new submission.** Reasons:
- V20 just submitted this session; needs ≥ 50 matches for stable estimate (currently 20).
- No offline code improvements since V20 merge — nothing new to submit.
- The #38 bug fix does not exist yet.

Leave V20 live, accumulate matches, and wait for #38 work.

## Open questions for next director

1. **Has V20 accumulated ≥ 50 matches?** If yes, is the score still ≤ 4.47 (fast-llm)? If yes, V20 is genuinely worse; if score climbs past 4.47, it was partner-sampling variance.
2. **Was #38 diagnosed offline?** Specifically: can we reproduce the "3 of 6 agents die step 4–15" behavior in an offline 8-agent self-play run? If yes, fix it; if no, the bug is online-env specific (different map, clips, initial spawn, something).
3. **Did #31 get resolved?** Experiment C (grep policy code for action ids 5–11) would close it in 5 minutes. If vibes genuinely never emit, every role-switching experiment we've run online has been measuring noise.
4. **Is `dinky:v27` code available?** Top-1 at 27.31 is 8× us. If their approach is documented in any leaked replay metadata or public repo, we should study it.
5. **Should we revert to `fast-llm-v1` behavior for 6+2 splits specifically?** A split-aware policy (use V20 in 4+4, use fast-llm in 6+2) would be a cheap blended submission if #38 proves hard to fix.
6. **Clean up branches**: 30+ remote branches still open. The session-8 merged branches (`amazing-meitner-JWpsV`, `amazing-meitner-ahBE5`, `amazing-meitner-cUcXZ`, `autoresearch-priority-issue-dAc9K`) can be deleted once nothing references them.
