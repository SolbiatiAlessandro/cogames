# Experiment Log: claude/amazing-meitner-aSOVe (Issue #58)

## Issue: 2-agent match handling — adaptive role assignment when n_agents <= 2

2026-05-02 00:00: autoresearch starting, my plan is to re-implement and extend the successful improvements from the previous researcher on branch claude/amazing-meitner-xfD6y (which was NOT merged). Their work took CvC 2-agent avg from 9.50 to 43.65. Key improvements to re-implement:

1. **Predicted miner station offset**: Navigate to (hub_row+4, hub_col+1) when miner station unknown but hub known (verified from BaseHub source code)
2. **SwitchableMiner**: Auto-switch miners to aligner behavior after repeated gear failures (safety net for congested stations)
3. **Fast get_heart re-selection**: After get_heart exits as stale near hub, skip explore and immediately retry from different approach side

Then push further with new ideas.

## Baseline

2026-05-02 00:00: starting to run baseline
