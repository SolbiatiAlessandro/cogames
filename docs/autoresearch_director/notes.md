# Director Notes
_Written: 2026-05-10 (Session 32)_

## What I observed

### Replay unavailable (same as session 30/31)
Python 3.11 on this machine still lacks `typing.override` (3.12+) in the cogames source code. Relied on online match data and researcher episode analysis instead.

### Online status — MASSIVE improvement since session 30

| Metric | Session 30 | Session 32 | Change |
|--------|-----------|-----------|--------|
| Best policy | v52 (#40, 36.15) | opt-v1 (#13, 40.07) | **+10.9% score, +27 ranks** |
| Gap to #1 | 5.71 pts (13.6%) | 1.79 pts (4.3%) | **-69% gap** |
| Variants tested | 1 (v52) | 21 (full A/B sweep) | new upload pipeline |

### What happened between sessions 30 and 32

1. **Session 31 (offline-to-online director)**: Diagnosed contamination-v64 crash as bundle shadowing. Created diagnostic path.
2. **Researcher 095mA**: Fixed the crash (upload_full_bundle.py), then ran 21 online A/B experiments. Found that:
   - `hearts<3 + wait<3` = +6 leaderboard pts (vs v52-clean baseline)
   - `JUNCTION_ALIGN_DISTANCE=25` is optimal
   - Contamination code actually HELPS online (v52-j25-fast #272 vs opt-v1 #13 with same J=25)
   - 19+ parameter variations all regressed vs opt-v1
3. **Researcher SamLl**: Junction distance fix (align=15/explore=25) gives +2.5% offline but was NOT the improvement online — J=25 for cascade is better online.

### opt-v1 match profile (25 completed CvC matches)

- Avg: 37.8, Median: 42.3, Min: 9.2, Max: 52.3
- By allocation: 2ag=24.5, 4ag=41.2, 6ag=44.0
- vs External partners (20): avg 38.0
- vs Internal policies (5): avg 36.8
- Top 5 partners give us 44-52 (competitive with anyone)
- Bottom matches (9-16) are with "ron.anticlips" weak/hostile partners

For comparison, #1 Softy:v96 has avg 36.5, min 3.2, max 55.5. Our raw match scores are already competitive — the Elo difference is mainly about match count accumulation.

## Current bottleneck

**Move failure rate (33% of aligner steps)** — agents waste 1/3 of steps bumping into walls and unknown obstacles. This is the strongest predictor of match score in the researcher's episode analysis. Created #69.

Secondary: **2-agent allocation weakness** (24.5 avg) drags overall rating. Created #70.

## What I expected to happen vs. what I found

**Expected (from session 30 notes)**:
- contamination-v64 would perform well online once crash fixed ✓
- Aligner throughput (#67) would be the top lever ✗
- 5A+3M might help now that mining is surplus ✗ (catastrophic)
- Heart queue wait reduction (6→3-4 ticks) might help ✓ (this was the key!)

**Found**:
- Contamination-v64 alone was neutral-negative online (v3 at #94, 33.95)
- The real improvement came from `hearts<3 + wait<3` (reducing hub dwell time)
- Combined with contamination code, this reached #13 — contamination helps by preventing gear loss
- Aligner throughput (#67) was exhausted after 19 experiments — ceiling is architectural
- The bottleneck shifted to raw navigation quality (move failures)

**Key surprise**: Online-offline gap inverted. Contamination was +15.2% offline but initially negative online. The hearts<3/wait<3 change was tested online-first and immediately improved leaderboard. This validates online-first methodology.

## Issues updated this session

- **#68**: CLOSED. Crash fixed by upload_full_bundle.py. opt-v1 reached #13.
- **#67**: CLOSED. Exhausted (19 experiments). Junction ceiling is architectural.
- **#65**: DEMOTED to priority:3. Subsumed by #67 findings.
- **#62**: DEMOTED to priority:3. Subsumed by #67 findings.
- **#69**: CREATED (priority:1). Move failure rate reduction — 33% of steps wasted.
- **#70**: CREATED (priority:2). 2-agent allocation performance gap.

## Merges this session

- **hearts<3/wait<3 change**: Applied to main (1 line in machina_llm_roles_policy.py)
- **upload_full_bundle.py**: Copied from 095mA branch to main
- **Did NOT merge 095mA HEAD**: Contains hub_weight=0.1 and blacklist changes that regressed

## Branches NOT merged (and why)

- **095mA HEAD** (09502f7): hub_weight=0.1 + map pollution changes regressed from opt-v1.
- **SamLl** (451be74): Junction dist split +2.5% offline but J=25 cascade is better online.
- **IgXg8** (b5c06d5): Same as SamLl + .pyc files committed.
- **OPj3g**: Issue #67 offline experiments. All exhausted.
- **wf6SN** (7f3d1ea): Previous director notes only.
- Old (NNt07, VZvye, C4lUC, q8Otj, dCgfY, 0S1xy): Stale since session 29-30.

## Submission status

- **beta-cvc**: opt-v1:v1 at #13 (40.07). 25 matches, stable. Best ever.
- **beta-teams-tiny-fixed**: Not checked this session.

## Open questions for next director

1. **Is the rating still converging?** With only 25 matches, opt-v1 may climb higher as Elo stabilizes. Check if score has changed.
2. **Move failure rate — can it be fixed?** Removing move_blocked_cells HURT (095mA v14-v18). The fix isn't "remove bad blocks" — it needs fundamentally better exploration. This is a hard problem.
3. **Online-first methodology**: Confirmed this session. Next researcher should upload early and iterate on online data rather than spending days on offline tuning.
4. **Stale branch cleanup**: 80+ remote branches. NNt07, VZvye, C4lUC, q8Otj, IgXg8, dCgfY, 0S1xy all confirmed stale and can be deleted.
5. **Partner interaction**: Worst matches (9-16) are with "ron.anticlips" policies. Are these actively adversarial or just weak? Could defensive play help?
6. **Match count effect**: Softy:v96 likely has 100+ matches giving tighter Elo estimate. Our 25 matches may have inflated variance penalty. Simply accumulating more matches might close the gap without any code changes.
