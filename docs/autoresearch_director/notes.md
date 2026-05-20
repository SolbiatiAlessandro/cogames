# Director Notes
_Written: 2026-05-20 (Session 36)_

## What I observed in the replay

Could not run replay — this container lacks `cogsguard` native module (requires bazel build). Used TSV data, issue comments, branch diffs, and online leaderboard API instead.

## Current bottleneck

**AUTH TOKEN EXPIRED (#78).** This is the #1 blocker for the entire research program. The Softmax auth token `6PnHPiX9...` resolves to `subject_type: anonymous`. No policy can be submitted — not scripted, not RL. This has been blocking for 5+ consecutive director sessions (34-38). Owner must run `cogames auth login` from a machine with a browser.

Secondary bottleneck: RL training maturity. All RL checkpoints on competition map score 0.05 (base alive reward). The distribution shift problem (max_dist=6/10 trained models fail at competition max_dist=15) is the core issue. Direct real-map training is the correct approach but is still early (held ticks at 793, growing slowly).

## What I expected to happen vs. what I found

**Expected** (from session 35 notes):
1. RL Phase 2 (max_distance=10) would progress — PARTIALLY: Phase 2 compmap shows 21K held in training but only 0.31 at eval
2. Auth blocker resolved — NO: Still expired. 5th consecutive session.
3. Submit to beta-teams-tiny-fixed — NO: Can't submit anything without auth
4. Merge SZmUt training scripts — BYPASSED: krCLo branch had better improvements to merge
5. Branch cleanup — DEFERRED: ~120 remote branches, but auth is higher priority

**Found**:
1. krCLo branch had clean +4.4% offline improvement (3A5M + hearts5 + progress fix) — MERGED to main
2. RAxer "critical bugs" mostly don't apply to current code. Only dead cooldown code (no effect).
3. Previous longep3k_e20 checkpoints LOST — never committed to git. Major research asset gone.
4. Real-map RL training (max_dist=15) is the most promising approach — started from previous e050 checkpoint
5. softy-rl:v1 at 12.26 online — even strong teams' RL is terrible online. RL-online gap is massive.
6. Gryffindor:v11 entered leaderboard at #12 (40.82). New competitor.

## Merges this session

- **claude/amazing-meitner-krCLo** -> main (fast-forward)
  - 3A5M role split: `aligner_fraction` 0.5 -> 3/8
  - Hearts accumulation: threshold 3 -> 5
  - Progress tracking bug fix: `last_heart_count` tracking
  - get_heart_cooldown_steps activation (cosmetic, no effect)
  - TSV evidence: 1153 vs 1060 baseline, 6-seed validated
  - Also includes: `train_curriculum.py`, `eval_rl_checkpoint.py` scripts

## Issues updated this session

- **#78**: CREATED (priority:1). Auth token expired blocker. Owner action required.
- **#76**: DEMOTED priority:1 -> priority:2. Blocked on #78. RL checkpoints lost.
- **#77**: KEPT at priority:2. krCLo merged. Needs online submission (blocked on #78).
- **#75**: DEMOTED priority:1 -> priority:2. RL still early, distribution shift is core problem.
- **#41**: DEMOTED priority:1 -> priority:2. RL-online gap may be much larger than expected.

## Submission status

- **beta-cvc**: evyIm-73a-stuck15:v1 at #5 (41.85). FROZEN — can't submit.
- **Main has krCLo improvements** ready to submit as `lessandro-ohm-mani-padme-hum` once auth works.
- RL policies NOT submitted — all score 0.05 on competition map anyway.

## Open questions for next director

1. **Is auth fixed?** Check `cogames auth status` — if still anonymous, escalate further. Consider alternative auth methods.
2. **Should we submit the krCLo scripted improvements?** Once auth works: submit as `lessandro-ohm-mani-padme-hum` to beta-cvc.
3. **Is the real-map RL training working?** Check krCLo branch (sessions 6+) for max_dist=15 results. Held ticks must reach ~7000+ to be competitive.
4. **Branch cleanup**: 120+ remote branches. Most are stale. Safe to prune.
5. **RL online expectations**: softy-rl:v1 at 12.26 suggests RL may not be the path to top-3. Scripted ceiling at 41.85 may be closer to the practical limit.
6. **Junction saturation**: krCLo found 51/53 junctions aligned by ~2K steps. After that, all reward is pure hold time. Defense against enemy scramblers is the real online lever.
7. **New season?** Check if new tournament seasons have opened.
