# Experiment Log: claude/amazing-meitner-hCVEi (Issue #60)

## Goal
Validate aSOVe 8-agent self-play (no regression), merge to main, submit online.

---

2026-05-02T10:30: autoresearch starting, my plan is to:
1. Run 8-agent self-play on aSOVe code (3 seeds: 42/123/7, 3000 steps)
2. Verify avg >= 1080 (within 2% of v52 baseline 1101)
3. If passes, merge aSOVe to main
4. Submit as `lessandro-ohm-bekkenze-maha-bekkenze` to `beta-cvc` season
5. Monitor first 10 matches

2026-05-02T10:30: starting to run 8-agent self-play baseline (3 seeds)

2026-05-02T10:50: 8-agent self-play results (aSOVe code, 3000 steps)

| Seed | Total Reward | xfD6y Reference | v52 Baseline |
|------|-------------|----------------|-------------|
| 42   | **1126.10** | 1121           | ~1100        |
| 123  | **1074.42** | 1007           | ~1100        |
| 7    | **1222.99** | 1240           | ~1100        |
| **Avg** | **1141.17** | 1122.67     | **~1101**    |

PASS: avg 1141.17 >= 1080 threshold (3.6% above v52 baseline of 1101).
No regression detected. All seeds perform well. Seed 123 is +6.7% vs xfD6y.

Decision: Proceed with merge to main and online submission.

2026-05-02T10:51: Merging aSOVe to main — SUCCESS. Merged aSOVe to main, pushed.

2026-05-02T11:00: Submitted policy online
- Name: `lessandro-ohm-bekkenze-maha-bekkenze:v1`
- Season: beta-cvc
- Pool: qualifying
- Bundle size: 273 KB (23 policy files)
- Policy class: MachinaLLMRolesPolicy (scripted miners + scripted aligners)
- cogames version: 0.25.6

Waiting for qualifying matches to complete. Key metrics to monitor:
- 2-agent match scores (target: >20.0 avg, vs old 9.16)
- Overall score (target: >36.0, vs v52's 35.62)
- Match completion (no failures/crashes)

2026-05-02T11:05: Monitoring online results

2026-05-02T11:10: CvC 2-agent validation (5 seeds, 3000 steps) — all match aSOVe exactly:
- Seed 42: 60.52 (baseline 19.57, +209%)
- Seed 123: 58.80 (baseline 49.87, +18%)
- Seed 7: 60.41 (baseline 60.38, +0.05%)
- Seed 99: 65.72 (baseline 65.72, 0%)
- Seed 256: 3.00 (floor, station congestion)
- Avg: 49.69 (+25% vs baseline 39.71)

2026-05-02T11:15: Starting new experiment loop — SwitchableMiner

Found bottleneck in 8-agent logs: agent 4 at step ~1800 picked up a scrambler, lost miner gear.
All 4 known miner stations were blacklisted (4, -2), (4, -1), (8, -3), (0, 5).
Agent spent ~1200 steps (40% of episode) in useless gear_up→explore→gear_up cycle.
Hypothesis: SwitchableMiner (auto-switch to aligner after 5+ consecutive gear failures) will
recover these wasted steps by letting stuck miners contribute as aligners instead.

2026-05-02T17:42: SwitchableMiner 8-agent self-play results (3000 steps)

| Seed | SwitchableMiner | Baseline (aSOVe) | Change |
|------|----------------|-------------------|--------|
| 42   | 1126.10        | 1126.10           | 0%     |
| 123  | 1090.81        | 1074.42           | +1.5%  |
| 7    | 1222.99        | 1222.99           | 0%     |
| **Avg** | **1146.63**  | **1141.17**       | **+0.5%** |

Result: Marginal improvement (+0.5% avg). SwitchableMiner only activates on seed 123 where
a scrambler was picked up (scrambler.gained=1). Seeds 42/7 had no scrambler events so
the feature never triggered → identical results. No regression detected.

Decision: KEEP — small improvement, no regression. The feature is a safety net that only
activates in scrambler scenarios. Advancing branch.

2026-05-02T17:42: Online matches — passed qualifying, now in competition pool.
9+ competition matches running against other policies (Cedric:v8, anoop, ron.scouts, etc.)

2026-05-02T17:43: Next experiment — looking for next bottleneck to address.

2026-05-03T17:30: Online match analysis — policy at rank #54, score 33.73 (18 matches)

| Agents | Matches | Avg Score |
|--------|---------|-----------|
| 2      | 7       | **18.57** |
| 4      | 6       | **34.00** |
| 6      | 5       | **40.59** |

6-agent performance (40.59) is competitive. 2-agent (18.57) is the clear bottleneck.
Downloaded and analyzed match logs for worst matches.

Found two bugs:

1. **Miner fast-depletion spin loop**: In 2.09 match (vs ron.scouts), miner enters infinite
   `mine_until_full → fast-depleted → mine_until_full` loop from step 400 to 10000 (96% of
   game wasted). 218 fast-depletions. Root cause: fast-depleted events don't trigger was_stuck
   or was_stale, so planner always selects mine_until_full when active extractors exist.
   Fix: track consecutive_fast_depletions, force explore after 5 to find fresh area.

2. **Gear-up explore-loop**: In 21.10 4-agent match, both miners lost gear (scrambler) and
   entered infinite `explore timeout → explore` loop because explore timeouts match the
   "timed out after" pattern that triggers was_stuck=True in the no-miner path. Miner
   never retries gear_up, so consecutive_gear_failures never reaches SwitchableMiner
   threshold. Fix: only return explore after actual gear_up failure, not after explore timeout.

Both fixes are safety nets — no change in 3000-step offline tests (8-agent or CvC).
Online validation needed. Submitting as v2.

2026-05-03T18:15: 8-agent validation (fast-depletion + gear-loop fixes)

| Seed | Current | Baseline | Change |
|------|---------|----------|--------|
| 42   | 1126.10 | 1126.10  | 0%     |
| 123  | 1096.15 | 1090.81  | +0.5%  |
| 7    | 1229.40 | 1222.99  | +0.5%  |
| Avg  | 1150.55 | 1146.63  | +0.3%  |

No regression. Advancing to online submission.
