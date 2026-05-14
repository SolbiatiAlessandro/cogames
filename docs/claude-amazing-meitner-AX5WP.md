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
