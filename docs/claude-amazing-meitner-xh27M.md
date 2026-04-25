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

## Experiment 2: Reduce cooldown over-blocking — FAILED, REVERTED

2026-04-25T17:28: hypothesis was that MOVE_COOLDOWN=6 is too aggressive.
Changes: cooldown TTL 6→3, deposit stale min 6→10, clear cooldowns on skill change.

Result: WORSE. 131.37 → 112.46 total reward. max_steps_without_motion 47 → 253.
Cooldowns actually HELP navigation by forcing agents to find alternative paths.
Clearing on skill change was especially bad — stale cooldowns represent real walls.

Learning: cooldowns are GOOD for the BFS pathfinding. Don't reduce them.

---

## Experiment 3: Increase stuck_threshold 20→30 — FAILED, REVERTED

2026-04-25T17:33: hypothesis was that agents abort too early.
Changes: stuck_threshold 20→30 (deposit timeout 40→60, mine timeout 100→150).

Result: WORSE. 131.37 → 96.22 total_reward (-26.7%). Hearts dropped 33→29.
Agents waste more time stuck instead of switching to productive alternatives.

Learning: stuck_threshold=20 is already well-tuned. Don't increase it.

---

## Experiment 4: Reduce aligner_fraction 62.5%→50% — SUCCESS, KEPT

2026-04-25T17:36: key observation from logs: aligners are heartless 59% of the time
(54/91 decision points). With 5 aligners competing for hearts from 3 miners, there's
a severe production bottleneck.

Changes: aligner_fraction for ≥6 agents: (n-3)/n → 0.5. Gives 4A+4M instead of 5A+3M.

Result: IMPROVED. 5-seed validation (seeds 42-46):
- 4A+4M avg: 122.64 (137.78, 91.74, 109.78, 164.04, 109.86)
- 5A+3M avg: 115.63 (131.37, 91.41, 136.45, 108.97, 109.95)
- Improvement: +6.1% on average

Learning: heart production was the bottleneck, not junction coverage. 4 productive
aligners beat 5 idle ones. High seed variance (91-164) driven by map layout.

---

## Experiments 5-7: Navigation improvements — ALL REVERTED

Tested three navigation changes, all neutral on 5-seed average:
- Exp 5: deposit retry with rotated side (avg 121.34 vs 122.64)
- Exp 6: increase HUB_ALIGN_DISTANCE 25→30/40 (avg 122.02/116.95 vs 122.64)
- Exp 7: gear_up approach side diversification (avg 123.34 vs 122.64)

Learning: navigation improvements help some seeds but hurt others. The variance
is dominated by map layout (corridor width, hub position) not agent behavior.
Move failures are 3.2% on good maps vs 12.9% on bad maps.
