# Autoresearch Issue 37: Submit merged V20 policy + validate at 8 agents / 10k steps

Branch: `claude/amazing-meitner-13pMr`
Target issue: [#37](https://github.com/SolbiatiAlessandro/cogames/issues/37) — priority:1

**Issue direction:** The merged V20 stack (issue #36) has massive offline improvements
that have NEVER been submitted to the online tournament. The currently submitted
policy predates ALL improvements from the last 3 sessions. Submitting the merged
code should yield a significant online score increase.

**Success criteria (from issue):**
- Online score >= 5.0 (from current 3.12, +60%)
- 8-agent config: >= 0.5/agent at 1k steps (>= 4.0 total)
- 8-agent 10k: all agents survive to step 10000

**Key context:**
- Current branch is fresh off main (9b4c2d9) which is the merged V20 stack.
- V20 work was done at 3 agents (2A1M). The new target is validating that
  the fixes also work at 8 agents, which is what online play uses.
- Session 7 on 8A (exp4, 3A5M) reached 5.84 total = 0.73/agent at 1k.
- This branch does NOT yet have fresh code of its own — the baseline IS the
  merged V20 code at 8A.

**Config under test (from issue):**
```
cogames play -m cogsguard_machina_1 -c 8 \
  -p class=machina_llm_roles,kw.num_aligners=3,kw.num_scouts=0,kw.stuck_threshold=28,kw.llm_timeout_s=10 \
  -s 1000 -r log --autostart
```

---

## 2026-04-14T17:18:00Z: autoresearch starting, my plan is to...

1. Run baseline: the merged V20 code at 8 agents / 1k steps, with the
   recommended config from the issue (3A5M scripted miners, stuck_threshold=28).
2. Compare to session 7 exp4 result (5.84 total / 0.73 per agent) and
   session 7 best (7.96 total / 0.995 per agent).
3. If baseline hits >= 4.0 total at 1k, proceed to 10k steps to check
   mortality and long-horizon reward.
4. Iterate on top: tune stuck_threshold, per-role phase-handling, LLM prompts.
5. Ultimate deliverable: a config that gives >= 5.0 online score and >= 4.0
   at 1k / 8 agents offline.

Note: without a GitHub API write token, issue comments can't be posted
directly from this container (the git proxy only passes git ops, not the
REST API). Progress will be fully logged in this file; it can be
mirrored to a comment by the human or director later.

---

## 2026-04-14T17:45:00Z: starting to run baseline

Config (from issue #37):
```
cogames play -m cogsguard_machina_1 -c 8 \
  -p class=machina_llm_roles,kw.num_aligners=3,kw.num_scouts=0,kw.stuck_threshold=28,kw.llm_timeout_s=10 \
  -s 1000 -r log --autostart --seed 42
```
Commit: 9b4c2d9 (main merged V20). LLM miners (default; not scripted_miners).

## 2026-04-14T17:55:00Z: baseline result is

**mission_reward: 6.125 total / 0.77 per agent at 1000 steps, seed 42.**
- aligned.junction.held (cogs): 6656 / (clips): 21040
- aligned.junction.gained: 19
- heart.withdrawn: 6 (initial 5 + 1 crafted via make_heart)
- heart gained total (agents): 13+4+2 = 19 hearts aligned junctions
- carbon.deposited 200, oxygen 100, germanium 140, silicon 160 — well balanced
- deaths: 2 (agent 3 and agent 7, both miners)
- gear: 4 miner, 3 aligner equipped at end; only 1 scout.lost + 1 aligner.lost total
- agent 2 had 591 action.failed (stuck-heavy)
- agent 7 had 53824 cell.visited — explored a LOT before dying

**Analysis:** This exceeds the issue #37 primary (>4.0), matches the stretch (5.0 online=>0.63/agent),
and BEATS the session 7 exp12 3-seed-avg (4.97 total). On seed 42 alone, V20 is
significantly stronger than session 7. Key evidence of V20 fixes working:
- Element balance: all 4 elements deposited within 2x of each other (V15 fix)
- Gear contamination low: 1 aligner.lost, 1 scout.lost (mostly V11/V12 fixes)
- 19 aligned.junction.gained >> 9 in session 7 exp4 (>2x)

**Baseline is strong enough to justify submission right now.** But the issue also
asks us to validate at 10k steps and across 8 agents. I should also run
alternate seeds to confirm it's not a seed-42 fluke (session 7 exp14 showed 2.51-7.96 range).

Total agent-lived stats:
- total heart.gained: 13+4+2+0+0+0+0+0 = 19 (aligners captured hearts)
- miners 3,4,5,6,7 deposited but never aligned (expected)
- total junction.aligned_by_agent: 13+4+2 = 19 (matches junction.gained)

Next experiments (in order):
1. **Seed sweep**: rerun baseline at seeds 43, 44 to confirm not a seed-42 fluke
2. **10k baseline**: run the 10k variant to check mortality (success criterion)
3. **Experiments beyond baseline**: if there's time, try LLM fast-path (skip LLM when
   decision is deterministic) to save tokens + latency, or try scripted_miners=true
   to see if that boosts further.

