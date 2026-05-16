# Director Notes
_Written: 2026-05-16 (Session 35)_

## What I observed in the replay

Ran 500-step replay with 4 agents (3 aligners + 1 miner) on the scripted policy:

- **Reward growth is linear**: 0.08/100 steps, reaching 0.41/agent at 500 steps
- **Agents cluster in center** (rows 48-60): no agent reaches map corners where junctions are at rows 6-7 and 91-92
- **Skill distribution**: explore 37%, get_heart 35%, align 9%, mine 8%, deposit 7%, gear_up 3%
- **High get_heart call rate** (35%) with only 9% align confirms hub depletion as the operational bottleneck — agents keep seeking hearts they can't get
- **All roles function correctly**: gear_up -> get_heart -> explore -> align cycle is intact
- **Miner works well**: mine_until_full -> deposit_to_hub cycles cleanly, finds 15 extractors

The scripted policy works but is fundamentally capped by: hub heart depletion, center-biased navigation, and inability to learn from experience.

## Current bottleneck

**RL training maturity.** The scripted policy is at its ceiling (#5 online, 41.85) and there are no further scripted improvements to make. RL training had a genuine breakthrough (first junction alignment on competition map via curriculum training) but is still 2.5x below scripted performance offline (0.072 vs 0.18 at 500 steps).

The specific RL bottleneck is **navigation on 88x88 map with 13x13 observation window**: agents can't see junctions 15+ tiles from hub, so they need curriculum training (close junctions -> medium -> full distance) to learn the navigate -> align sequence.

Key RL training findings:
- CPU training works: 226K-2.8M params at 2.4-4K SPS. No GPU needed.
- 5-action space (noop + 4 moves) eliminates entropy collapse, matches top policies
- Entropy annealing (0.08 -> 0.01 over 30 epochs) prevents universal collapse
- Training metrics are misleading: random map seeds average lucky outcomes. Always eval on fixed seed.
- Arena (50x50) to competition (88x88) transfer fails. Must train directly on competition map.
- Behavioral cloning kills entropy, making RL fine-tuning impossible.

## What I expected to happen vs. what I found

**Expected** (from session 34 notes): evyIm-73a stabilizes, RL remains blocked on GPU, branches stay unmerged.

**Found**:
1. evyIm-73a-stuck15 STABLE at #5 (41.85) -- exactly as expected.
2. RL training DID start! Owner said "we don't need GPU" -- unblocked everything. Multiple sessions ran 20+ configs.
3. RL BREAKTHROUGH: curriculum training (max_distance=6) produced first junction alignment on competition map.
4. RL still early: 0.072 reward/500s vs scripted 0.18. Training-eval gap is large.
5. Tournament submission blocked by 401 auth -- no RL policies submitted online yet.
6. New competitors: slanky:v171 (#7, 41.28), Paz-Bot-9000:v47 (#10, 41.10) entered top 10.

## Issues updated this session

- **#75**: CREATED (priority:1). RL Curriculum Training Phase 2+3 -- specific actionable issue with proven configs and branch to continue from.
- **#41**: KEPT at priority:1. Added comprehensive director update on breakthrough.
- **#74**: DEMOTED to priority:2. Scripted ceiling is documented fact, action on RL.
- **#73**: DEMOTED to priority:3. A/B testing exhausted.
- **#71**: DEMOTED to priority:3. Junction efficiency addressed by RL.

## Merges this session

None. No branches have competitive results to merge.

## Branches reviewed (NOT merged)

- **claude/amazing-meitner-SZmUt** (7 ahead): Curriculum training BREAKTHROUGH. train_curriculum.py, eval scripts, Phase 1 weights. NOT MERGED -- RL eval still below scripted. Next researcher should continue from here.
- **claude/amazing-meitner-0j5Ye** (many ahead): Exhaustive RL config exploration. 70 files changed. NOT MERGED -- experimental infrastructure.
- Remaining 40+ branches: all stale from previous sessions.

## Submission status

- **beta-cvc**: evyIm-73a-stuck15:v1 at #5 (41.85). Stable. No new submission.
- **beta-teams-tiny-fixed**: New season, no entries from us. Low priority.
- RL policies NOT submitted -- 401 auth blocker.

## Open questions for next director

1. **Has RL Phase 2 (max_distance=10) progressed?** Check SZmUt branch for results beyond epoch 18.
2. **Is the 401 auth blocker resolved?** RL needs online validation to calibrate offline->online gap.
3. **Should we submit to beta-teams-tiny-fixed?** New season might be easier to compete in.
4. **Should we merge SZmUt training scripts to main?** Infrastructure value vs cleanliness tradeoff.
5. **Branch cleanup**: 40+ remote branches, most stale. Safe to prune after review.
6. **New competitors**: slanky and Paz-Bot-9000 entered top 10. Are they RL? What's their approach?
7. **Has the wider leaderboard shifted?** Softy hasn't pushed new versions since v111. Are they still iterating?
