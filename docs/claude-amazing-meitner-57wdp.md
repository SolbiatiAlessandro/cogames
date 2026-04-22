# Experiment Log: claude/amazing-meitner-57wdp

## Issue: #44 — Miner productivity plateau + #45 — Online submission

## 2026-04-22T05:25: Autoresearch starting

**Plan**: 
1. Upload merged #44 improvements (move cooldown + cascade priority) to tournament (issue #45)
2. Continue #44 experiments to improve miner productivity at longer episode lengths
3. Focus on extractor depletion radius, progressive exploration, and mining throughput

**Context**: Previous researchers (QzSVo branch) achieved +79.2% improvement with:
- Move cooldown (+52.9%): Per-agent 6-step cooldown prevents congestion deadlock
- Cascade priority (+17.2%): Hub-biased junction scoring for faster cascade unlock
- Remaining issues: deposit plateau at ~3-5k steps, extractor depletion

## 2026-04-22T05:35: Online submission (issue #45)

- Uploaded `lessandro-scripted-v37:v1` to beta-cvc (WITHOUT merged code — mistake)
- Discovered QzSVo improvements were not merged into working branch
- Merged QzSVo into working branch (fast-forward)
- Uploaded `lessandro-scripted-v38:v1` to beta-cvc WITH all improvements
- Also uploaded `lessandro-scripted-v37-teams:v1` to beta-teams-tiny-fixed

## 2026-04-22T05:48: Baseline run (with merged #44 improvements)

Seed 42, 3000 steps, 8 cogs:
- **avg_reward_per_agent: 110.35**
- junction.aligned_by_agent: 47
- heart.gained: 50
- death: 1
- max_steps_without_motion: 94
- move.failed: 1836, move.success: 22164 (92.4% success rate)

This matches QzSVo's cascade priority result (110.35 for seed 42). Baseline confirmed.

## 2026-04-22T05:50: Starting multi-seed baseline
