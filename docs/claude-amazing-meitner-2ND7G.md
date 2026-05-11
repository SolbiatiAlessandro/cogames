# Experiment Log: claude/amazing-meitner-2ND7G
## Issue #71: Junction control efficiency — 74% vs Softy's 84%

2026-05-11T08:00: autoresearch starting, my plan is to improve junction control efficiency from ~74% to >80% of possible junction-time. The key levers from issue analysis are:
1. Junction targeting priority — cascade scoring improvements 
2. Multi-aligner coordination — prevent duplicate targeting + add re-targeting
3. Hold vs expand tradeoff — defend held junctions, especially after hearts run out
4. Faster initial claiming — reduce time-to-first-junction-aligned
5. Agent lifespan equalization — more consistent agent survival times

Starting with a baseline run at 3000 and 10000 steps to establish current performance.

2026-05-11T08:00: starting to run baseline

2026-05-11T08:30: baseline result is:
- 3k steps: total_reward=1026.8, junction.aligned_by_agent=51, heart.gained=57
- 10k steps: total_reward=3938.9, junction.aligned_by_agent=51 (SAME!), heart.gained=57 (SAME!)
- Key finding: ALL alignment happens in first 3k steps. Remaining 7k steps produce ZERO new hearts/alignments
- Root cause: after initial hearts (5 from hub) + early crafted hearts are consumed, aligners switch to "defend" mode after just 1 get_heart timeout (20 stale steps). Defend lasts 1000 steps before retrying. Cycle is too slow.
- Hub has plenty of resources for ~76+ more hearts (oxygen bottleneck: 536 remaining / 7 per heart), but aligners don't visit often enough

2026-05-11T08:45: starting new experiment loop, in this experiment I want to try aggressive heart retry.
My hypothesis is: by increasing get_heart_timeouts threshold (1→4) and reducing defend duration (1000→200 steps), aligners will retry hearts much more frequently and capture crafted hearts from deposits, dramatically increasing junction alignments in mid-late game.

Changes:
1. get_heart_timeouts threshold: 1 → 4 (more patience before giving up)
2. defend duration: stuck_threshold * 50 (1000) → stuck_threshold * 10 (200)
