# Experiment Log: claude/amazing-meitner-AX5WP

## Issue: #71 - Junction control efficiency

2026-05-14 00:00: autoresearch starting, my plan is to:
1. Run baseline on current code (commit 14c7ac6)
2. Integrate the proven improvements from toEqP researcher that were NOT merged:
   - aligner_fraction=0.6 (5A+3M for 8 agents)
   - HUB_ALIGN_DISTANCE=30 (more junctions directly alignable)
   - stuck_threshold=15 (faster stuck detection)
   - Heart accumulation: heart_count<5, stale timeout<8
   - Aligner spread bonus in cascade_priority_target
   - Miner junction deposit
3. Validate each change incrementally with multi-seed testing
4. Upload best configuration to online tournament

Key context from previous researchers:
- toEqP achieved 3.991 avg reward (+48.4% from 2.690 baseline) but was NOT merged
- Director noted conflicts with proven navfix code
- Online score: navfix-cd3:v1 at #14 (40.60)
- Junction efficiency gap: 74% vs Softy's 84%

2026-05-14 00:01: starting to run baseline

2026-05-14 05:18: baseline result is 1101.7 avg (5-seed: 1026.8+1068.3+1177.9+1141.6+1093.8) at 3000 steps, 8 agents self-play. ~51 junctions aligned per seed.

2026-05-14 06:00: starting new experiment loop. Integrating toEqP improvements incrementally. Found and fixed a critical bug: heart progress tracking in _update_progress() - state.last_has_heart was updated BEFORE the made_progress check, so heart acquisition NEVER counted as progress. Aligners were leaving hub after just 3 stale ticks instead of accumulating hearts.

2026-05-14 06:30: Combined changes tested (5A+3M, stuck=15, HUB_ALIGN=30, bug fix, spread bonus, hearts<3). Result: 1125.5 avg (+2.2%). Junctions increased from ~51 to ~57.4 avg. Hearts gained up from 63.2 to 67.4 avg.

2026-05-14 07:00: Tried heart accumulation thresholds <4 and <5. Both WORSE — excess hoarding (10-22 unused hearts at end). Hearts<3 is the sweet spot: enough to chain 2 alignments per hub trip, not so many that aligners waste time at hub.

2026-05-14 07:05: Tried stuck_threshold=10. Worse (-1.2%) — agents give up on navigation too quickly. Stuck=15 is optimal.

2026-05-14 07:10: Tried 6A+2M (aligner_fraction=0.75). Much worse (-7.5%): gear contamination increases with more aligners near same stations, and 2 miners can't produce enough resources.

2026-05-14 07:30: Important finding from step-rate analysis:
- 500 steps: 24 junctions (46% of total)
- 1000 steps: 42 junctions (81%)
- 1500 steps: 51 junctions (98%)
- 2000+ steps: 51-52 junctions (plateau)
Junction claiming is COMPLETE by step 1500. Remaining 1500-10000 steps are pure holding time. Key insight: EARLIER claiming = more holding time = more reward.

2026-05-14 07:50: Tried miner junction deposit. Confirmed the game mechanic exists (junction.py has queryDeposit handler), but implementation causes regression (-4.3% to -6.8%). Miners get stuck navigating to junctions, reducing both mining and junction alignment throughput. The concept works but needs more sophisticated routing.

2026-05-14 08:00: Tried aggressive navigation shake (fire at 3/2 instead of 5/3). Much worse (-3.7%): the random direction attempts themselves fail, causing even MORE move failures (3612 vs 2319 baseline). Reverted.

2026-05-14 08:10: Key observation: move failures tripled from 787 (original baseline) to 2319 with our changes. The 5A+3M config creates more congestion near hub. But the extra aligner throughput more than compensates for the congestion cost. One agent was stuck for 170 consecutive steps — a target for future optimization.

## Best config so far: +6.4% (commit 7076aba)
- HUB_ALIGN_DISTANCE=35 (was 25 in baseline)
- Aligner spread bonus (-0.05 * min_dist_to_others) in _cascade_priority_target
- Enemy recapture priority (-8 bonus for enemy junctions, no effect in self-play but helps online)
- All other parameters at baseline values (4A+4M, stuck=20, hearts<3 wait)
- Synergy: HUB_ALIGN=35 and spread bonus work together — without spread, HUB=35 gives same results as HUB=30

2026-05-14 10:30: Session 2 findings:
- Environment produces different absolute numbers than session 1 (~846 vs ~1102 baseline avg)
- Relative comparisons are still valid
- Re-baselined all comparisons: baseline 14c7ac6 = 846.2 avg (5 seeds)
- Key discovery: HUB_ALIGN=35 is sweet spot (30=+2.7%, 35=+6.4%, 40=+3.3%)
- Previous session's changes (5A+3M, stuck=15, heart bug fix) ALL hurt in current env
- Heart bug "fix" actually reduces throughput (faster hub exit is better)
- Move cooldown reduction (6→3): -5%, too many failed navigations
- Return_load parameter (2/3/5) has zero effect — miners always deposit 1 resource at a time
- 776-step stuck period on seed 45 is game-level physics, not fixable by policy
- Junction blacklisting on stuck exit has zero effect (wrong skill diagnosed)
- Uploaded: ax5wp-v2-hub35:v1 to Softmax tournament

## Next steps for future researchers
- Check online tournament performance of ax5wp-v2-hub35:v1
- Try longer episodes (10k steps) to validate improvement scales
- Investigate the game-level stuck periods (not policy-addressable with current approach)
- Try adaptive explore strategies to speed up initial junction discovery
- Consider different hub_dist weight (currently 0.2) in cascade scoring
- Try 3A+5M for extra mining throughput (since 4A+4M > 5A+3M)
