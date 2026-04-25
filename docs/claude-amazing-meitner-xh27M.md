# Experiment Log: claude/amazing-meitner-xh27M

## Issue: #49 — Submit v43 with partner robustness fix

2026-04-25T17:14: autoresearch starting, plan is to:
1. Merge partner robustness fix from Y1TiB branch (dynamic role assignment + adaptive return_load)
2. Validate offline with 8 agents and 4+4 noop split
3. Upload as v43 to beta-cvc
4. Also close #48 (crash-prevention wrappers already on main)

Context: v42:v1 is our best at #105/229 (score 18.74, 34 matches). v42:v2/v3 failed (None scores — likely resubmission issue). The partner robustness fix from #47 branch Y1TiB was NOT yet merged to main despite being referenced as "merged" in #49.

2026-04-25T17:14: starting to run baseline

2026-04-25T17:16: baseline result (pre-merge, main @ cbbc1e9):
- 8 agents, 500 steps, seed 42: total_reward=32.82, avg=4.10/agent
- Role assignment: STATIC — agents 0-4 aligner, 5-7 miner
- Problem: if tournament gives us IDs 0-3 in 4+4 split → ALL aligners, 0 miners

2026-04-25T17:16: merged Y1TiB branch (fast-forward to 761fcb5):
- Dynamic proportional role assignment: A,M,A,M,A,A,M,A pattern
- Adaptive return_load: <3 miners → cargo threshold drops from 40→26

2026-04-25T17:17: post-merge validation:
- 8 agents, 500 steps, seed 42: total_reward=32.72, avg=4.09/agent (no regression)
- Role assignment: PROPORTIONAL — A,M,A,M,A,A,M,A (5A+3M interleaved)
- 4+4 noop test, 500 steps, seed 42: total_reward=27.14, avg=3.39/agent
  - 4 real agents get A,M,A,M (2 aligners + 2 miners) — correct!
- 8 agents, 1000 steps, seed 42: total_reward=131.37, avg=16.42/agent

2026-04-25T17:22: uploaded lessandro-scripted-v43:v1 to beta-cvc
- Bundle: 79 KB, 23 files
- Policy class: MachinaLLMRolesPolicy (scripted miners + scripted aligners)
- Added to qualifying pool

Expected impact: v42's bad-partner matches scored 0-2 (10 of 34 matches). With the fix,
those matches should score 10-15+ since we'll now have miners even with weak partners.
Average score should jump from 18.74 → ~25+, improving rank from #105 → ~#80-90.

## Next steps
- Wait for 5-10 matches to complete on v43
- Check split-specific scores (4+4 and 6+2 splits)
- If v43 shows improvement, move to further offline reward optimization

---

## Experiment 2: Reduce cooldown over-blocking (navigation efficiency)

2026-04-25T17:28: starting new experiment loop, in this experiment I want to try reducing
cooldown-induced navigation failures. My hypothesis is that the current MOVE_COOLDOWN=6
and deposit stale threshold=6 are too aggressive, causing agents to abort skills prematurely
when they're adjacent to targets but transiently blocked by other agents.

Analysis of 1000-step baseline:
- 784 failed moves (9.8%), 96 stuck/stale events, 47 max steps without motion
- 29 mine stale exits, 19 deposit stale exits
- junction.aligned_by_agent=32 but agents waste ~10% of steps stuck

Changes:
1. MOVE_COOLDOWN: 6 → 3 (both llm_skills.py and aligner_agent.py)
2. Deposit stale threshold: max(6, threshold//3) → max(10, threshold//3) 
3. Clear cooldowns on skill transition to prevent stale paths carrying over
