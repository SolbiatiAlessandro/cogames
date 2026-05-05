# Experiment Log: claude/amazing-meitner-q8Otj

## Issue: #62 — Junction capture rate & exploration coverage

**2026-05-05 00:00**: Autoresearch starting. Working on issue #62 (junction capture rate & exploration coverage).

Director session 26 found that:
- Score ≈ junction_held / 10000 — junction control IS the scoring mechanism
- Good matches: 2.6x more unique cells visited, 4.4x more junctions captured
- Agent mortality was previously misdiagnosed as bottleneck — zero deaths in 3/3 replays
- The lever is exploration coverage (finding junctions) and capture speed (aligning them quickly)

**Plan**: Improve how agents explore and capture junctions. Key ideas:
1. Increase exploration radius / frontier selection to discover more junctions
2. Reduce time wasted on non-productive activities (waiting, backtracking)
3. Improve junction target selection for aligners (prioritize undiscovered territory)
4. Reduce move failures which waste steps

**2026-05-05 00:01**: Starting baseline run.

**2026-05-05 00:05**: Baseline results (2 seeds, 8-agent, 3000 steps):
- Seed 42: total_reward=1126.10, junction.aligned_by_agent=53, cell.visited=2,159,824
- Seed 123: total_reward=1095.66, junction.aligned_by_agent=53, action.move.failed=1485 (6.2%)
- Average: 1110.88

**2026-05-05 00:06**: Starting experiment 1 — Increase exploration radius.

Hypothesis: The aligner hub tether (35 cells) and alignment distances (25 hub, 20 junction) were set conservatively based on the WRONG diagnosis that agents die from HP. Since Session 26 proved agents never die, we can safely expand exploration radius. More exploration → more junction discoveries → more captures → higher score.

Changes:
- _HUB_SEARCH_DISTANCE: 20 → 30
- _HUB_ALIGN_DISTANCE: 25 → 40 (junctions further from hub can be aligned)
- _JUNCTION_ALIGN_DISTANCE: 20 → 30 (cascade range increased)
- _MAX_ALIGNER_HUB_DISTANCE: 35 → 55 (aligner explores further before tether)
- _MAX_HUB_DISTANCE (miner): 40 → 50
