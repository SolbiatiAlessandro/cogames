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
