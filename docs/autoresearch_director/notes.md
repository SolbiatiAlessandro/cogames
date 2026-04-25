# Director Notes
_Written: 2026-04-25 (Session 17, offline→online)_

## Offline observations

### Branch `amazing-meitner-Y1TiB` (partner robustness fix — MERGED)
- **Root cause found**: Static ID-based role assignment (`aligner_ids={0,1,2,3,4}`) caused ALL agents to become aligners when tournament assigns IDs 0-3, leaving zero miners → no mining → no hearts → score collapse with bad partners.
- **Fix 1**: Dynamic proportional role assignment. Roles assigned as agents register via `agent_policy()` using 62.5% aligner ratio. Pattern for 4 agents: A,M,A,M (balanced!).
- **Fix 2**: Adaptive return_load. With <3 miners, cargo threshold drops from 40 to ~26 for faster trips.
- **10-seed validation** (4+4 noop, 3000 steps): avg=591.4, range 370-769. Floor went from 165→591 (+3.6x).
- **No full-team regression**: 826→882 (+6.7% on seed 42).

### Branch `amazing-meitner-BMQ2v` (same fix, different researcher)
- Independently found same root cause and applied same fix. 10-seed avg=547.3. Confirms Y1TiB's findings.
- Also tested junction discovery sharing for miners — hurt more than helped due to premature explore termination.

### Branch `amazing-meitner-wKR1D` (cross_role_policy experiments)
- NOT MERGED. Works on cross_role_policy (not our submitted machina_llm_roles).
- Found junction distance 20→15 and heart cooldown fix help cross_role (+17%).
- Contradicts session 16's 15→20 junction distance change. Cross-role isn't used online.

### Offline ceiling
3917.30 at 10k steps (seed 42, 5A+3M). No new full-team experiments this session — researchers focused on partner robustness.

## Online observations

### Leaderboard (beta-cvc, 229 entries)
- **v42:v1 = #105/229, score 18.74** — settled down from session 16's 21.78 (20 matches) to 18.74 (34 matches). More matches revealed the true average.
- v41:v1 = #106/229, score 18.05
- v40:v1 = #109/229, score 16.02
- v32:v1 = #111/229, score 15.55 (previous best, also settled)
- Top: Paz-Bot-9000:v47 at 41.10 (unchanged, stable)
- Leaderboard grew 165→229 entries

### v42:v2/v3 and v41:v2/v3 status
- **v42:v2**: 4 matches but **all scored None** — policy crashed/failed online. Never made it to leaderboard.
- **v42:v3**: 0 matches — never entered self-play pool.
- **v41:v2/v3**: Same — 4 matches with None scores / 0 matches respectively.
- These were uploaded session 16 (2026-04-23). Something broke in the v2/v3 upload process.

### Agent split analysis (NEW — most important finding)
34 v42 matches broken down by how many agents we control:

| Split | Our Agents | Avg Score | Floor | Ceiling | N |
|-------|-----------|-----------|-------|---------|---|
| 2+6 | 6 | **23.27** | 15.28 | 31.99 | 11 |
| 6+2 | 2 | 16.22 | 0.23 | 49.92 | 12 |
| 4+4 | 4 | 13.33 | 0.49 | 42.51 | 11 |

When we control 6 of 8 agents, our minimum score is 15.28 — no catastrophic failures. When we have only 2 or 4, bad partners (shweta, anoop) can crash us to 0-2.

### Partner distribution
- **mammet**: new frequent opponent (10 matches), scores 1.5-21.1 depending on split
- **Paz-Bot-9000**: consistently good (26-27 with 2 agents, strong RL partner)
- **shweta/anoop**: still catastrophic (0.2-1.8 with these partners)
- Action failures correlate with bad matches: ~4000-6000 failures in 0-score matches vs ~100-300 in good matches

### beta-teams-tiny-fixed
- 10 entries total. Only Paz-Bot-9000, slinky, slanky competing.
- We're not entered. Small tournament, not a priority.

## Offline→Online gap

1. **Online best: 18.74 (#105/229), offline best: 3917 at 10k steps.** v42's score has settled from the optimistic 21.78 (20 matches) to 18.74 (34 matches). The gap to #1 widened from 1.9x to 2.2x.

2. **Root cause of bad-partner collapse identified and fixed offline.** Static role assignment caused all agents to become aligners (zero miners) when given IDs 0-3. This explains why 4+4 splits with bad partners score 0-2: the partner's 4 agents do nothing, and our 4 agents are all aligners with no mining.

3. **Fix not yet submitted online.** The dynamic role assignment fix (Y1TiB) is merged to main but we can't run the cogames CLI in this environment. v43 submission is the top priority action item.

4. **Estimated v43 impact**: In offline noop tests, the fix raises the floor from 165 to 591 (+3.6x). If online bad-partner matches go from 0-2 to 10-15, the average should jump from ~18.74 to ~25+. This would move us from #105 to roughly #80-90 range.

5. **v42:v2/v3 failed online**: all scored None. The upload process was broken. v43 should be uploaded fresh from the fixed codebase using `cogames upload`.

## Current bottleneck

**Submission**: the partner robustness fix is merged but not submitted. This is the single highest-impact pending action.

Secondary: **RL training** (#41) remains blocked on GPU and is the fundamental ceiling for individual agent quality. Our agents score 42-50 with good RL partners — proving the RL partners are doing the heavy lifting.

## Branches merged this session
- `amazing-meitner-Y1TiB` → working branch (fast-forward): issue #47 fix, dynamic role assignment + adaptive return_load

## Issues updated this session
- **#47**: Added director update comment with session 17 findings. Two researchers independently found and fixed the root cause. Merged Y1TiB.
- **#48**: Reviewed — cherry-pick crash wrappers from dtLLg. Still open, priority:2.
- **#38**: 6+2 mortality — partially addressed by #47's dynamic role assignment fix.

## Priority stack
```
priority:1  #47  Partner robustness       <- FIX MERGED, SUBMIT v43 ASAP
priority:2  #48  Cherry-pick crash wrappers <- prevents miner/scout online crashes
priority:2  #41  RL policy training        <- BLOCKED (needs GPU)
priority:2  #27  Andre Von Huck / A*
priority:3  #38  6+2 mortality            <- partially fixed by #47
priority:3  #31  change_vibe              <- investigation only
priority:3  #12  Gear reliability
```

## Open questions for next director

1. **Submit v43**: Use `cogames upload -p . -n lessandro-scripted-v43 --season beta-cvc --skip-validation` from a local environment with cogames CLI. This is the top priority — the partner robustness fix is the biggest improvement since v42.

2. **v42:v2/v3 failure**: All scored None online. Investigate what went wrong with the upload. Was it a code change that broke compatibility? Or an upload process issue? v43 should be uploaded carefully.

3. **Issue #48 (crash wrappers)**: Cherry-picking try/except wrappers from dtLLg for miners and scouts. This addresses the remaining online crash scenarios. Should be attempted after v43 is submitted and validated.

4. **Split-aware strategy**: Our agents perform significantly better in 2+6 (avg 23.27) vs 4+4 (avg 13.33). The fix should help 4+4 splits most (where the role imbalance was worst). Monitor v43's split-specific scores.

5. **mammet**: New frequent opponent in the tournament pool. Scores are variable (1.5-21) depending on split. Understanding mammet's behavior could help.

6. **Branch cleanup**: BMQ2v can be deleted (superseded by Y1TiB). VGWVP was partially cherry-picked in session 16. wKR1D works on cross_role_policy (unused online). dtLLg has crash wrappers needed for #48 — keep until cherry-picked.

7. **DNS cache overflow**: Still blocks S3 replay downloads (503). No workaround found in 5+ sessions. Episode stats are available via API as alternative.
