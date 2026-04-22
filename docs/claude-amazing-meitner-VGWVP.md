# Experiment Log: Issue #46 — v37/v38 regression fix

## Branch: claude/amazing-meitner-VGWVP

2026-04-22 00:00: autoresearch starting, my plan is to:
1. Validate that the current branch code (which has all session 13+14 fixes merged) works correctly offline
2. Run baseline with 500 steps, 8 cogs, seed 42 (expect ~8+ total reward)
3. Upload the policy to Softmax as lessandro-scripted-v39
4. Monitor online match results for crashes and score improvements over v32 (16.87)
5. If baseline is solid, explore further improvements to maximize reward

The root cause of the v37/v38 regression was uploading from a branch that was missing:
- hub_deposits_total tracking
- Aligner extractor sharing
- Gear-up hazard fallback fixes
- Death-detected gear reset
- Correct role allocation (scripted_miners=True, num_aligners=min(4, n_agents//2))

This branch has all those fixes merged via session 15 director commit.

2026-04-22 17:25: starting to run baseline

2026-04-22 17:27: baseline results:
- **500 steps, 8 cogs, seed 42**: total_reward=34.26, avg_per_agent=4.28, 17 hearts, 4 miners + 4 aligners
- **3000 steps, 8 cogs, seed 42**: total_reward=789.18, avg_per_agent=98.65, 47 hearts, 43 junctions aligned
- **500 steps, 4 cogs, seed 42**: total_reward=18.26, avg_per_agent=4.56, 18 hearts, 2 miners + 2 aligners

All results are excellent. The 4-agent scenario confirms the role allocation fix works (2 miners + 2 aligners, not 0 miners + 4 aligners as in v37).

The 500-step 8-cog result (34.26) far exceeds the issue's ~8+ threshold.
Next: upload to Softmax as lessandro-scripted-v39.
