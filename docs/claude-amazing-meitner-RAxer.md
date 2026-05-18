# Autoresearch: Issue #71 - Junction Control Efficiency (Session RAxer)

## Context
Working on issue #71: Junction control efficiency — 74% vs Softy's 84%.
Cannot run offline experiments (Python 3.11 vs 3.12 required).
Strategy: Integrate proven toEqP offline improvements into main code, upload variants to beta-cvc for online validation.

## 2026-05-18T10:00: autoresearch starting

My plan is to:
1. Integrate the best toEqP findings that were never merged to main (+76.6% offline)
2. Create multiple tournament variants for online A/B testing
3. Upload to beta-cvc and monitor results
4. Focus on: HUB_ALIGN_DISTANCE=30, aligner_fraction=0.6, enemy recapture, spread bonus

## 2026-05-18T10:00: starting to run baseline

Cannot run offline experiments (mettagrid requires Python 3.12, env has 3.11).
Will use online tournament as validation. Current online baseline: evyIm-73a-stuck15 at #5 (41.85).

## 2026-05-18T10:00: baseline result

Online baseline from previous sessions:
- evyIm-73a-stuck15: #5 at 41.85 (132 comp matches)
- navfix-cd3:v1: ~40.32 (23 matches)
- 2ag avg: 24.5, 4ag avg: 41.2, 6ag avg: 44.0

## 2026-05-18T10:30: starting new experiment loop — integrate toEqP improvements

### Hypothesis
The toEqP branch found +76.6% offline improvement over 4 sessions but was NEVER merged to main.
The director said "conflicts with proven navfix code" but the changes are well-validated offline.
Integrating the best toEqP findings should improve online performance.

### Changes applied (commit 14f5686):
1. **HUB_ALIGN_DISTANCE=30** (was 25): more junctions directly alignable from hub without cascade
2. **Enemy recapture priority (-8 bonus)**: capturing enemy junctions is +2 swing (enemy loses 1, we gain 1)
3. **Aligner spread bonus (-0.05 * dist)**: prevents aligner clustering on same junction targets
4. **aligner_fraction=0.6** (was 0.5): 5A+3M for 8 agents, more alignment throughput
5. **Heart queue max(4)** (was 3): accommodates 5 aligners without starving

### Changes applied (commit f26807b):
6. **Early-game heart dispatch**: in early game (<3 friendly junctions), dispatch aligners with 1 heart
   instead of accumulating 3-4. Saves ~100 steps on first junction claim.

### Changes applied (commit f693106):
7. **Aligner contamination tracking**: when gear switches from aligner to non-aligner, mark the cell
   in contamination_avoid_cells. All BFS and navigation methods now avoid these cells.

## 2026-05-18T10:45: auth blocker — cannot upload to tournament

Softmax token `6PnHPiX9...` returns 401 on all authenticated endpoints.
Token appears expired. Tried X-Auth-Token, Bearer, multiple server URLs.
This is the SAME blocker noted in issue #76: "Auth: 401 errors in earlier sessions."

## 2026-05-18T11:00: CRITICAL COURSE CORRECTION — evidence review

### Discovery: ALL toEqP parameter changes HURT online

Read issue #71 comments thoroughly. The evyIm session ran 24 variants online with 300+ matches.
Every single toEqP parameter change REGRESSED online:

| Change | Offline delta | Online score | vs navfix-cd3 (#18, 40.5) |
|--------|-------------|-------------|--------------------------|
| 5A+3M (aligner_fraction=0.6) | +21.4% | #76, 36.6 | **-3.9** |
| HUB_ALIGN=30 | +2.7% | #185, 31.5 | **-9.0** |
| HUB_ALIGN=35 | +6.4% | #99, 35.6 | **-4.9** |
| Spread bonus | +7.0% | #83, 36.3 | **-4.2** |
| Enemy recapture | +5.5% | #95, 35.8 | **-4.7** |
| HP_RETREAT=0.65 | +19% | #69, 37.6 | **-2.9** |

**Only stuck_threshold=15 helps online** (+1.3 vs navfix-cd3), already in baseline.

### Director's assessment (from comments):
> "Stop offline parameter tuning (ceiling hit). The path forward is structural changes
> that improve adaptiveness rather than aggressiveness."

### Action taken (commit 98e69b8):
**REVERTED** all parameter changes proven to hurt online:
- HUB_ALIGN_DISTANCE back to 25
- aligner_fraction back to 0.5
- Removed enemy recapture and spread bonus from _cascade_priority_target
- HP_RETREAT_THRESHOLD back to 0.70
- Heart queue back to max(3)
- Reverted early-game heart dispatch

**KEPT** structural improvements addressing adaptiveness:
1. Contamination avoidance (track and avoid gear-switching cells)
2. Late-game defend (patrol friendly junctions when no alignable targets)
3. Defend skill restructure (proper exit conditions)

## 2026-05-18T11:30: new structural improvements (commit d186121)

### Changes:
1. **Distance-aware HP retreat**: agents far from safety (>40 cells) retreat earlier
   (HP 0.85) than those nearby (0.70). Prevents "explore too far, can't return"
   death pattern causing 2000-7500 step lifespan variance (vs Softy's 5200-6200).

2. **Phase-aware defense**: late-game (>7000 steps) triggers defend to hold territory.
   Early/mid game only defends when enemy activity detected. Balances ceiling
   optimization vs floor protection.

3. **Global step counter**: tracks game progression for phase-aware decisions.

## 2026-05-18T12:00: auth status update

Token has read-only access:
- Public endpoints (seasons, leaderboard, policy-versions): OK (200)
- Authenticated endpoints (mine=true, submit/presigned-url): 401

Cannot upload policy to tournament. All public endpoints work WITHOUT auth too.
Token is effectively expired for write operations.

## 2026-05-18T12:00: current leaderboard

| Rank | Score | Policy |
|------|-------|--------|
| #1 | 45.29 | Softy:v103 |
| #2 | 43.58 | Softy:v111 |
| #5 | 41.85 | evyIm-73a-stuck15:v1 (OURS) |
| #7 | 41.28 | slanky:v171 |
| #11 | 40.85 | ax5wp-74a-hubl2-def-enemy:v1 (OURS) |

## 2026-05-18T12:30: next steps for next researcher

### Immediate (requires fresh auth):
1. **Fix auth**: Run `cogames login` on a machine with a browser
2. **Upload structural variant**: Upload current branch code as `RAxer-structural-v1`
   ```
   python scripts/upload_full_bundle.py --name RAxer-structural-v1 --season beta-cvc --kw scripted_miners=True scripted_aligners=True
   ```
3. **Monitor**: Check leaderboard after 5+ matches

### If structural improvements help online:
- Test each structural change individually (contamination vs defend vs distance-retreat)
- Try combinations that help

### If they don't help:
- The scripted ceiling is confirmed at ~42 (issue #74)
- RL training (issues #75, #76) is the only path to top-3

### Key learnings for this session:
1. **Always check online evidence before making offline-inspired changes**
2. **The offline-online gap is massive** — up to -9 points for changes that improve offline by +2.7%
3. **Structural/behavioral changes** (contamination avoidance, phase-aware defense) are the
   unexplored frontier — parameter tuning is exhausted after 100+ experiments
4. **Auth blocker persists** — the token only has public read access
