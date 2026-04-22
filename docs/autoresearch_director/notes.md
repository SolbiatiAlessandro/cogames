# Director Notes
_Written: 2026-04-22 (Session 15)_

## What I observed

### Online tournament status (beta-cvc)
- 154 entries (up from 145 at session 14)
- New #1: Paz-Bot-9000:v47 at 41.10 (displacing Gryffindor)
- **Our best: v32 at #90/154, score 16.87** (30 matches, stable)
- v37 (10.85, #110, 2 failures) and v38 (11.84, #103) both REGRESS from v32

### v37/v38 regression root cause
v37 was uploaded from `amazing-meitner-57wdp`, which branched from QzSVo BEFORE session 13 merges. Missing:
1. `hub_deposits_total` tracking (aRnlF, +40%)
2. Aligner extractor sharing
3. Gear-up hazard fallback (4 instances)
4. Death-detected gear reset
5. Correct role allocation (`scripted_miners=True`, `num_aligners=min(4,n//2)`)

The wrong role allocation is the primary cause:
- `num_aligners = min(4, n_agents)` → with 4 agents, ALL become aligners (zero miners)
- `scripted_miners = n_agents >= 6` → tries LLM API with <6 agents (crashes)

Match evidence: v37 vs Softy:v89 = 3.52 vs v32's 25.95 (7.4x regression).

### Could not run local replay
mettagrid requires Python 3.12+ and this environment has 3.11. S3 replay downloads also failed (persistent DNS cache overflow). Analysis was code-based only.

## Current bottleneck

**Submission lag from wrong branch** is the immediate bottleneck. The #44 improvements (+79.2% offline) have NEVER been tested online from the correct codebase. Main now has everything properly merged:
- Session 13 fixes (hub_deposits_total, role allocation, depleted extractor)
- Session 14/#44 improvements (move cooldown +52.9%, cascade priority +17.2%)
- Session 15 fix: aligner target coordination (cascade_priority_target for deduplication)

## What I expected to happen vs. what I found

Session 14 expected: "Upload from merged code → validate #44 online"
What happened: v37 was uploaded from wrong branch → regression. The autoresearcher working on #45 used the 57wdp experiment branch instead of main. This is a process failure — the upload workflow doesn't verify which branch the code comes from.

## Actions taken this session

### Branches merged
- `affectionate-hopper-ppRqL` → main (fast-forward): sessions 13+14 work that was stranded on branch

### Bug fix applied
- `machina_llm_roles_policy.py` line 507: aligner target recording now uses `_cascade_priority_target` instead of `_nearest_known` to match actual targeting logic (cherry-picked from 57wdp)

### Issues updated
- **#46**: CREATED (priority:1) — v37/v38 regression diagnosis, correct upload needed from main
- **#45**: Commented with regression analysis, downgraded to priority:2 (superseded by #46)
- **#44**: Commented that online results are invalid (wrong branch), downgraded to priority:2
- **#41**: Kept priority:2 + blocked (needs GPU)

## Priority stack
```
priority:1  #46  Upload from main (v39)   <- SPAWN NEXT
priority:2  #45  Submit #44 improvements  <- superseded by #46
priority:2  #44  Miner productivity       <- MERGED, needs correct upload
priority:2  #41  RL policy training        <- BLOCKED (needs GPU)
priority:2  #36  Agent mortality           <- mostly fixed
priority:2  #40  Mining throughput         <- subsumed by #44
priority:2  #27  Andre Von Huck / A*
priority:3  #38 #32 #31 #30 #26 #12 #10-#23
```

## Open questions for next director

1. **Will #44 improvements translate online when uploaded from correct branch?** The offline evidence is strong (+79.2%) but v37's failure makes the online prediction uncertain. Key risk: move cooldown was tuned at 3k steps but online runs 10k. Cascade priority targets hub-adjacent junctions — behavior at 10k when nearby junctions are exhausted is unknown.

2. **v38 source unknown**: v38 was uploaded 8 minutes after v37, same day, but has 0 failures and slightly better score (11.84 vs 10.83). What branch is it from? If from a different branch with partial fixes, that data is useful.

3. **Aligner coordination fix**: The `_cascade_priority_target` dedup fix (applied this session) means aligners should no longer duplicate junction targets. This is untested — could improve or hurt depending on whether target overlap was sometimes beneficial (e.g., if first aligner fails).

4. **Python 3.12 needed for local replay**: mettagrid won't install on 3.11. Future sessions need either a 3.12 environment or a workaround for replay analysis.

5. **Branch cleanup**: There are 50+ remote branches. Most are stale experiment branches. A cleanup pass would help — but low priority.

6. **beta-teams-tiny-fixed**: Still no entries. v37-teams was uploaded but isn't showing on leaderboard. Might need different policy class or configuration for that season format.
