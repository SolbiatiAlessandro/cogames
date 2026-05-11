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

2026-05-11T09:00: experiment 1 result (aggressive-heart-retry, commit b978ab1):
- Self-play neutral: all alignment still completes by step 3000, so no measurable difference
- Expected online benefit: aligners retry hearts more aggressively after enemy scrambles junctions
- Keeping this change as it improves robustness without regression
- Also tested cascade weight 0.5 and 0.7 — variance-neutral, reverted
- Also tested heart batch 3→5 — slightly regressive (-2.1%), reverted

Key insight: self-play saturates at step 3000 (all junctions aligned). Testing improvements to mid/late-game recovery requires adversarial play. Self-play is only useful for testing early-game efficiency and preventing regressions.

2026-05-11T09:15: deep analysis of aligner bottleneck.
- Oxygen plateau (900 by step 2000) isn't the bottleneck — 54/57 hearts ready by step 1000
- The real bottleneck: 65% of aligner time is `alignable=0` (has heart, no junction to align)
- This is because the cascade distance is 15 cells (game engine), and junctions become alignable in waves
- Between waves, all 4 aligners idle exploring. After all junctions aligned, all idle.
- Tested JUNCTION_ALIGN_DISTANCE fix (25→15 to match game engine): +0.6% only, marginal
- Tested cascade-aware scoring (prefer junctions that unlock more): more junctions aligned (53-55 vs 51) but LOWER reward — aligners travel farther, delaying early alignments
- Tested directional aligner exploration: -0.5%, reverted
- Tested 5 aligners / 3 miners: -5.5%, mining bottleneck

2026-05-11T10:00: experiment 2 — junction deposit for miners (+4.7%).
Hypothesis: miners can deposit at friendly junctions (which route to hub), saving travel time.
Junction deposit handlers route elements to the hub automatically.

Changes: added `_nearest_deposit_target()` in llm_skills.py. When miner is full, check if nearest friendly junction is >5 cells closer than hub. If so, deposit there.

5-seed results:
- Seed 42: 1076.8 (baseline 1026.8, +4.9%)
- Seed 123: 1120.8 (baseline 1076.3, +4.1%)
- Seed 7: 1224.0 (baseline 1117.6, +9.5%)
- Seed 99: 1096.9 (baseline 1103.2, -0.6%)
- Seed 256: 990.0 (baseline 934.9, +5.9%)
- 5-seed avg: 1101.7 (baseline 1051.8, **+4.7%**)

Also tried conservative threshold (10 cells closer): +2.3% (worse). Keeping threshold 5.
