# Director Notes
_Written: 2026-04-21 (Session 14 — offline-to-online)_

## Offline observations

### Issue #44 improvements (move cooldown + cascade priority)
- **Move cooldown**: +52.9% avg reward at 3k steps (57.97 → 88.64). Deaths 12→1 (92% reduction). Move failures reduced 68-80%.
- **Cascade priority**: additional +17.2% (88.64 → 103.90). Hub-biased junction targeting with weight=0.7.
- **Combined**: +79.2% from baseline. 3-seed average at 3000 steps, 8 cogs.
- Extractor depletion tracking: neutral at 3k but enables 10k scaling (deposits plateau at 3k but reward scales linearly from energy/survival).
- These were on `amazing-meitner-QzSVo` branch — merged this session with conflict resolution.

### Session 13 merges (already on main via vigilant-feynman)
- aRnlF: hub_deposits_total fix (+40% at 10k)
- ccN7G: Role allocation fix (4A4M always, no scouts)
- Fb3vU: Depleted extractor adjacency fix (+55% junctions)

### Conflict resolution
- llm_skills.py had 3 conflicts between session 13 (Fb3vU) and QzSVo:
  1. Extractor selection: combined hub-weighted selection WITH depletion filtering (best of both)
  2. HP retreat threshold: accepted QzSVo's 0.25 (was 0.70 from Fb3vU, 0.50 original). QzSVo evidence: +52.9% with 92% fewer deaths. The move cooldown prevents congestion-death, making aggressive HP retreat unnecessary.
  3. Move target recording: accepted QzSVo's approach (needed for cooldown system to track move failures).

## Online observations

### Leaderboard status
- beta-cvc: 145 entries (up from 123 at session 12)
- **Our best: v32 at #85/145, score 16.97 ±12.93** (29 matches)
- v33 at #87/145, score 15.42 (25 matches)
- v35 at #108/145, score 10.02 — REGRESSION
- v36 at #104/145, score 10.73 — REGRESSION
- Top: Gryffindor:v11 at 40.82 (unchanged)
- v34 still broken (WebSocket crash, #43)

### Score evolution
- v32: 12.66 (session 12, 20 matches) → 16.97 (session 14, 29 matches). Score IMPROVED with more data.
- Rank dropped from #68/123 to #85/145 due to 22 new competitors joining.

### v35/v36 regression analysis
- v35 (score 10.02) and v36 (score 10.73) both worse than v32 (16.97)
- v35 was uploaded from Fb3vU branch after diagnosing v34 crash — may have introduced the aggressive HP retreat (0.70) that hurts productivity
- v36 has mortality-related changes from dtLLg branch (ship-proximity retreat) — adds complexity without clear benefit
- Neither v35 nor v36 includes the issue #44 move cooldown fix — the single biggest improvement (+52.9%)

### v32 replay analysis (new finding!)
**Match: v32 vs slinky:v3, score=52.22** (4+4 agents, cooperative):
- Our agents survive 5913-6506 / 10000 steps (**59-65%**) — dramatically better than session 12's 15-31%
- slinky:v3 agents survive only 1953-3162 / 10000 (20-32%) — we OUTLIVE the partner!
- 522,165 junction.held, 126 junctions gained
- 2200 carbon, 2150 germanium, 2160 oxygen, 2160 silicon deposits (excellent balance)
- Zero vibe transitions (universal, not a bug)

### Match patterns (v36 data, 22 matches)
- With strong RL partner (2 our agents + 6 strong): 41-54 score (partner carries)
- With medium partner (4+4 or 6+2): 5-22 score (mixed)
- With weak partner (2+6 or 4+4 weak): 0.8-1.4 score (true level)
- Agent split (2/6 vs 4/4 vs 6/2) dramatically affects score

## Offline-to-online gap

1. **Offline best**: 103.90/agent at 3k steps (issue #44, merged this session). Online best: #85/145, score 16.97.
2. **Gap cause**: The #44 improvements (+79.2%) are NOT in any submitted policy. v32 (our best online) predates all session 13 and #44 fixes.
3. **Submission lag is the primary gap**: We have significantly better code that hasn't been tested online.
4. **v35/v36 regression confirms**: Not all offline changes translate to online improvement. The move cooldown + cascade priority specifically target congestion and junction control — these should translate well.
5. **Agent survival is no longer the bottleneck**: v32 replay shows 59-65% survival, competitive with or better than partners.

## Current bottleneck

**Submission lag**: The merged #44 improvements need to be uploaded and tested online. This is the single highest-leverage action.

Secondary: RL training (#41) is the fundamental ceiling. Our best scripted policy scores 16.97 vs RL's 40.82 (2.4x gap). Even with #44 improvements, we're unlikely to close this gap without RL.

## Branches merged this session

1. **vigilant-feynman-nYLeQ** (fast-forward): Session 13 work — aRnlF + ccN7G + Fb3vU merges
2. **amazing-meitner-QzSVo** (conflict resolved in llm_skills.py): Issue #44 move cooldown + cascade priority + extractor depletion tracking

## Issues updated this session
- **#44**: Commented with merge status and online submission needed
- **#36**: Downgraded to priority:2 — agent survival mostly fixed (59-65% in v32 replay)

## Priority stack
```
SUBMIT NEXT:
  Upload new policy with #44 improvements (move cooldown + cascade priority)

priority:1  #44  Miner productivity       <- MERGED, needs online submission + validation
priority:1  #41  RL policy training        <- BLOCKED (needs GPU)
priority:2  #36  Agent mortality           <- MOSTLY FIXED (59-65% survival)
priority:2  #40  Mining throughput         <- subsumed by #44
priority:2  #27  Andre Von Huck / A*
priority:3  #38 #32 #31 #30 #26 #12 #10-#23
```

## Open questions for next director

1. **Submit the merged code as v37+**. The cogames CLI is not available in this environment. Next session needs to either install it or use the API directly to upload.

2. **Will #44 improvements translate online?** Move cooldown (+52.9%) addresses congestion — highly likely to help online. Cascade priority (+17.2%) targets hub-adjacent junctions — should help with 10k scoring. HP retreat at 0.25 is aggressive — may increase deaths online but the cooldown compensates.

3. **v32 survival was better than expected (59-65%)**. Session 12 measured 15-31% in different matches. The difference is likely partner quality and agent count split (4+4 vs 2+6). With 4 agents, we have more map coverage and survival.

4. **beta-teams-tiny-fixed**: Still 10 entries, we have no entries. Low priority but easy to submit.

5. **dtLLg branch (ship-proximity retreat, v21-v30)**: NOT merged. The uploaded v22-v30 policies show mixed online results (v28 at 14.53, v22 at 9.83). The branch has no offline validation. Given that v32 already survives 59-65%, the ship-retreat code may not be needed. Skip unless online evidence shows mortality regression.

6. **RL training**: Still the fundamental ceiling (2.4x gap). When will GPU compute be available?
