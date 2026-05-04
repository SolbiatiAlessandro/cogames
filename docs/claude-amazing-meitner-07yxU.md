# Experiment Notebook: claude/amazing-meitner-07yxU

## Issue: #60 - Validate aSOVe 8-agent, merge, and submit 2-agent fix online

## 2026-05-04T00:00: autoresearch starting

**My plan is to:**
1. Run v52 baseline 8-agent self-play on seeds 42/123/7 at 3000 steps
2. Merge aSOVe branch changes (9 improvements for 2-agent performance)
3. Validate merged code on same seeds — target avg ≥1080 (within 2% of v52 baseline ~1101)
4. If validation passes, merge to main and submit online as v53
5. If server issue #59 is fixed, monitor first matches

**aSOVe branch improvements (from claude/amazing-meitner-aSOVe):**
- Predicted miner station offset navigation
- Hub approach rotation for aligners (rotate side every 2 failed get_heart)
- Miner station blacklisting after 4 failed gear_up attempts
- Hub rotation reset on successful heart withdrawal
- Defend duration reduced from 50x to 25x stuck_threshold
- Stale defend trigger after 6 consecutive get_heart stale exits
- Aligner _get_heart method override with preferred side rotation

**aSOVe 2-agent results:** baseline 39.71 → final 49.69 (+25%, +423% vs original 9.50)

## 2026-05-04T00:01: starting to run baseline

Running v52 baseline on main (commit cb45610) with 8 agents, 3000 steps, seeds 42/123/7.

## 2026-05-04T00:10: baseline results

| Seed | v52 Baseline | 
|------|-------------|
| 42   | 1121.22     |
| 123  | 1073.88     |
| 7    | 1204.06     |
| **Avg** | **1133.05** |

Baseline average 1133.05, above the issue's expected 1101.

## 2026-05-04T00:15: merged aSOVe and running validation

Merged origin/claude/amazing-meitner-aSOVe into current branch. Running same 3 seeds.

## 2026-05-04T00:25: aSOVe validation results — PASS

| Seed | v52 Baseline | aSOVe merged | Delta |
|------|-------------|-------------|-------|
| 42   | 1121.22     | 1126.10     | +0.4% |
| 123  | 1073.88     | 1074.42     | +0.1% |
| 7    | 1204.06     | 1222.99     | +1.6% |
| **Avg** | **1133.05** | **1141.17** | **+0.7%** |

Target was avg ≥1080 (within 2% of v52 baseline). Result: 1141.17 (+0.7% above baseline).
The aSOVe changes actually slightly IMPROVED 8-agent performance.

2-agent spot check (seed 42): total_reward=168.88 (84.44/agent). Dramatically improved from original 2-agent ~9-19 scores.

**Decision: PASS — proceed to merge and submit online.**

## 2026-05-04T00:30: merging to main and submitting online

Uploaded as `lessandro-scripted-v59:v1` to beta-cvc tournament.
- Policy version ID: c758167d-8b56-463d-80c4-db54d94bcc9e
- Added to pools: qualifying
- Server issue #59 appears fixed (upload succeeded)

Current online state:
- Our best: v52 at #29, score 36.11
- Target: >36.0 online score
- v59 includes all v52 improvements + aSOVe 2-agent fixes

## 2026-05-04T00:35: monitoring and next steps

v59 is now qualifying. The 2-agent improvements should boost our overall score since ~35% of matches are 2-agent.

**Next experiment:** While waiting for v59 results, let me look for additional improvements. The aSOVe branch also showed that the 8-agent performance was slightly improved (+0.7%), suggesting the hub rotation and station blacklisting help even in 8-agent scenarios. Let me look for further gains.
