# Director Notes
_Written: 2026-04-23 (Session 16, offline→online)_

## Offline observations

### Branch `amazing-meitner-pzwh4` (source of v42, our new online best)
- Hub approach diversification: +6.2% at 10k (seed 42), +35.5% (seed 123), +51.4% (seed 7 at 3k)
- Deposit stuck loop fix + extractor depletion tracking: 2.3x mining throughput
- 5A+3M role allocation for 8 agents: +9.3% over 4A+4M
- Best: 3917.30 reward at 10k steps (seed 42)

### Branch `amazing-meitner-VGWVP` (source of v39, v40)
- Hub approach diversification: +6.4% to +12.8%
- Deposit side rotation: +12.1%
- Junction align distance 15→20: +2.2% (3k seed 42), +18.7% (3k seed 123)
- Best: 913.13 reward at 3k steps

### Offline ceiling
The offline reward continues improving: 3917 at 10k steps is 6.4% above the session 15 baseline (3682). The trend is positive but flattening — most gains now come from mining efficiency and hub congestion reduction rather than new strategies.

## Online observations

### Leaderboard (beta-cvc, 165 entries)
- **v42:v1 = #90/165, score 21.78** — NEW BEST (+29% vs v32's 17.38)
- v41:v1 = #95/165, score 17.70 (+2%)
- v40:v1 = #99/165, score 17.18 (-1%)
- v39:v1 = #100/165, score 16.63 (-4%)
- v32:v1 = #96/165, score 17.38 (baseline, slight decay with more matches)
- Top: Paz-Bot-9000:v47 at 41.10, stable
- New entrants: slinky:v3 (#7, 39.47), slanky:v155 (#8, 39.24), Paz-Bot-9000:v50 (#4, 40.33)

### v42 match analysis (20 matches)
Extreme partner dependence (stddev=12.6):
- With Gryffindor:v24: 49.92 (would be #1 if consistent!)
- With dinky_edsel:v12: 47.29
- With slinky:v5: 42.51
- With Paz-Bot-9000:v49: 26.68
- With shweta.v34:v1: 0.23
- With anoop.dazzle:v1: 1.78

### v42:v2/v3 and v41:v2/v3
Uploaded 2026-04-23 but NOT on the leaderboard yet. May need time to qualify through self-play pool before entering competition. Status unknown.

### Season updates
- beta-cvc: now version 8, "freeplay" format, compat 0.25
- beta-teams-tiny-fixed: NEW season created 2026-04-23 (team-based tournament format). Not yet investigated.

## Offline→Online gap

1. **Online best: 21.78 (#90/165), offline best: 3917 at 10k steps.** The offline→online correlation is positive: pzwh4's improvements (hub diversification, mining fixes, 5A3M) translated to a +29% online improvement. This confirms we're optimizing the right things offline.

2. **Gap narrowing: 2.4x → 1.9x.** At session 15 the gap to #1 was 2.4x (16.87 vs 41.10). Now it's 1.9x (21.78 vs 41.10). Progress is real.

3. **Partner sensitivity is the dominant online factor.** With good partners we score 42-50 (competitive with #1). With bad partners we score 0-2. Since partners are random, our average is heavily influenced by the partner quality distribution.

4. **The remaining gap is NOT primarily offline quality.** Our agents perform at top-10 levels when paired with good partners. The bottleneck is:
   a. Bad partners tank scores (100x worse than good partner games)
   b. Fundamental RL vs scripted ceiling for individual agent actions

5. **No replay analysis possible.** S3 downloads and the Softmax API both return "DNS cache overflow" (503) for binary data. Code-based analysis only.

## Current bottleneck

**Partner robustness** (#47). Our average score is dragged down by 0-2 point matches with bad partners. If we could raise the floor from ~0 to ~10 on these matches, our average would jump from ~22 to ~27+. This is a bigger lever than further offline optimization.

Secondary: **RL training** (#41) remains blocked on GPU and is the fundamental ceiling.

## Branches merged this session
- `amazing-meitner-pzwh4` → my branch (fast-forward): v42 source, hub diversification, 5A3M, mining fixes

## Code changes applied this session
- Junction align distance 15→20 (cherry-picked from VGWVP, +2.2% evidence)
- Merged pzwh4: aligner hub approach diversification, deposit stuck loop fix, extractor depletion tracking, 5A+3M role allocation, explore timeout

## Issues updated this session
- **#46**: CLOSED (v37/v38 regression resolved — v42 proves correct branch works)
- **#45**: CLOSED (submit #44 — superseded by v42)
- **#44**: CLOSED (miner productivity — merged and validated online)
- **#47**: CREATED (priority:1 — partner robustness)
- **#32**: Upgraded priority:3→2 (partner robustness evidence from v42 match data)

## Priority stack
```
priority:1  #47  Partner robustness (bad partner → 0 score)   <- SPAWN NEXT
priority:2  #41  RL policy training        <- BLOCKED (needs GPU)
priority:2  #32  Partner robustness (general)  <- upgraded from p3
priority:2  #36  Agent mortality           <- MOSTLY FIXED
priority:2  #40  Mining throughput         <- subsumed by pzwh4
priority:2  #27  Andre Von Huck / A*
```

## Open questions for next director

1. **v42:v2/v3 and v41:v2/v3**: these were uploaded 2026-04-23 but don't appear on the leaderboard. Check if they qualified through self-play and entered the competition pool. If not, investigate why.

2. **beta-teams-tiny-fixed season**: new team-based tournament created today. Should we submit a policy? The format has multiple stages with progressive culling. Might favor different strategies than freeplay.

3. **Partner robustness testing**: the ideal offline test is 4 our agents + 4 noop agents. Can we simulate this? If our agents can score >10 in this setup (vs 0 with bad partners online), that confirms the hypothesis.

4. **DNS cache overflow**: still blocks S3 replay downloads and httpx API calls. Previous sessions have the same issue. Need a different environment or workaround for replay analysis.

5. **Branch cleanup**: VGWVP is partially subsumed by pzwh4. The junction distance change was cherry-picked. The deposit_side_offset approach in VGWVP differs from pzwh4's hub_approach_rotation but the TSV evidence favors pzwh4. VGWVP could be deleted after confirming all value is captured.

6. **Submission from merged code**: the current branch has pzwh4 + junction distance 20 — this is newer than v42. Should be uploaded as v43 and tested online. But first confirm whether the change improves things (the junction distance increase has moderate evidence).
