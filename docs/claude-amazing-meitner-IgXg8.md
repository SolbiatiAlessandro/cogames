# Experiment Log: claude/amazing-meitner-IgXg8 (Issue #65)

## Goal
Alignment speed: align junctions earlier in the first 2000 steps for higher junction.held in online play. The hypothesis is that aligning faster increases cumulative held time and thus online score.

## Background
- Issue #67 (aligner throughput, 19 experiments) found the junction count ceiling is architectural (~55-57 junctions at 3000 steps)
- The speed at which we REACH that ceiling matters for online (10k steps): earlier alignment = more cumulative junction.held
- Current v52 policy reaches full alignment at ~step 3000-4000 in self-play
- Post-contamination-fix baseline: 3.282 avg reward (5-seed)
- Online: v52 at rank #40, score 36.15. Gap to #1: 13.6%

## My Plan
1. Profile gear-up time: how many steps do aligners spend acquiring aligner gear?
2. Optimize aligner gear acquisition: expected station position, direct routing
3. Optimize junction ordering: nearest-first within cascade range
4. Try staggered heart acquisition to reduce hub congestion
5. Test effect of JUNCTION_ALIGN_DISTANCE variations

---

2026-05-09T00:00: autoresearch starting, my plan is to speed up junction alignment by optimizing gear acquisition, heart retrieval, and junction targeting order for aligners. The key insight from #67 is that junction COUNT is capped by map topology, so the lever is junction SPEED — getting to that cap faster.

2026-05-09T00:01: starting to run baseline (5 seeds: 42, 123, 7, 99, 555)

2026-05-09T00:30: baseline results (note: mettagrid 0.15.0 reward scale differs from earlier sessions)

| Seed | Reward (per agent) | Junction Held | Junction Gained | Hearts Gained | Hearts Withdrawn |
|------|-------------------|---------------|-----------------|---------------|-----------------|
| 42   | 130.05            | 127050        | 50              | 61            | 21              |
| 123  | 133.94            | 130936        | 55              | 69            | 22              |
| 7    | 137.90            | 134906        | 59              | 70            | 19              |
| 99   | 135.20            | 132196        | 54              | 63            | 22              |
| 555  | 148.01            | 145009        | 59              | 68            | 19              |
| **Avg** | **137.02**     | **134019**    | **55.4**        | **66.2**      | **20.6**        |

Key observations:
- junction.gained averages 55.4, consistent with #67's architectural ceiling of ~55-57
- junction.held averages 134019 — this is cumulative held time, our primary metric for #65
- hearts withdrawn only 19-22 — matches #67 findings
- Reward is deterministic (all 8 agents get identical reward per seed)

Now analyzing aligner timing to find where speed improvements are possible.

### Alignment Rate Profile (seed 42)

| Steps | Junctions Gained | Junction.Held | Pct of Final |
|-------|-----------------|---------------|-------------|
| 200   | 8               | 945           | 16%         |
| 500   | 30              | 7,746         | 60%         |
| 1000  | 48              | 29,003        | 96%         |
| 1500  | 48              | 53,003        | 96%         |
| 2000  | 49              | 77,215        | 98%         |
| 3000  | 50              | 127,050       | 100%        |

Key finding: alignment is **96% complete by step 1000**. Only 2 more junctions are added in steps 1000-3000. The critical window is steps 200-500 where 22 junctions are aligned (44% of total).

---

## Experiment 1: Reduce heart accumulation <4 to <2 — DISCARDED (-0.01% avg)
Flat result, essentially no effect. Heart accumulation timing doesn't matter at 3000 steps.

## Experiment 2: Fix JUNCTION_ALIGN_DISTANCE mismatch (25→15)

2026-05-09T02:00: starting new experiment. The game engine uses `CvCConfig.JUNCTION_ALIGN_DISTANCE=15` but our policy uses `_JUNCTION_ALIGN_DISTANCE=25`. This means aligners target junctions 16-25 cells from the nearest friendly junction, where cascade alignment silently fails (heart consumed with no effect). The #67 researcher on branch OPj3g found this fix gave +2.5%, but it was never merged to main.

My hypothesis: fixing this mismatch will improve reward because:
1. No wasted hearts on impossible alignments (travel to junction + timeout)
2. Aligners focus on actually-alignable junctions within 15 cells
3. Faster cascade progression since aligners don't waste time on unreachable junctions

Change: `_JUNCTION_ALIGN_DISTANCE = 25` → `_JUNCTION_ALIGN_DISTANCE = 15` in aligner_agent.py
