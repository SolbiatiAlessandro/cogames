# autoresearch: issue #77 — Dynamic Role Switching + Architectural Changes

Branch: `claude/amazing-meitner-v1EZZ`
Target issue: [#77](https://github.com/SolbiatiAlessandro/cogames/issues/77) — priority:2

## Context

Previous 7 sessions on #77 exhausted incremental parameter/mechanism tweaks, reaching a +3.9% ceiling after 55+ experiments. This session focuses on **architectural changes** that haven't been attempted:

1. **Dynamic role switching**: Convert aligners to miners after junction saturation
2. **Aligner idle detection**: Aligners that spend >N steps exploring without finding junctions switch to mining
3. **Multi-agent deposit coordination**: Stagger deposit trips to reduce hub congestion

Key finding from prior sessions: aligners spend 68% of time exploring, 84% of explore phases cap out without finding junctions. Junction alignment saturates by step ~1200. After that, aligners are pure dead weight.

## Plan

2026-05-21T08:00Z: autoresearch starting, my plan is to:
1. Run baseline with merged dz2Gf improvements (3-seed avg at 3000 steps)
2. Implement dynamic aligner→miner role switching after junction saturation
3. Test variations: switch threshold, partial vs full switching
4. If that works, try more architectural changes

## Log

2026-05-21T08:00Z: starting to run baseline

### Baseline (3A/5M, merged dz2Gf)
| seed | reward |
|------|--------|
| 42 | 1139.17 |
| 43 | 1159.65 |
| 44 | 1268.85 |
| **avg** | **1189.22** |

### Exp 1: Mining mode (aligner→miner after junction saturation)
Implemented dynamic role switching: after 3 consecutive fruitless explores and 20+ friendly junctions, non-sentinel aligners switch to mining (gear up as miner, mine extractors, deposit to hub). One aligner (lowest ID) stays as sentinel.

Result: **Perfectly neutral** — identical rewards to baseline (1189.22 avg). Mining mode activates correctly at step ~500 after junctions saturate, but extra mining doesn't help because hearts aren't the bottleneck in offline eval (66 hearts produced vs 53 needed).

Keeping the code for potential online benefit (more hearts for re-capture after enemy scrambles).

### Exp 2: 4A/4M split
| seed | reward | junctions | hearts |
|------|--------|-----------|--------|
| 42 | 1085.22 | 52 | 63 |
| 43 | 1030.26 | 56 | 71 |
| 44 | 1233.42 | 62 | 78 |
| **avg** | **1116.30** | | |
**Result: -6.1% — DISCARD.** More aligners paradoxically hurts because 4 miners can't produce hearts fast enough.

2026-05-21T06:42Z: Pivoting to capture speed optimization experiments

### Exp 3: return_load=20
avg 1116.00 → **-6.2% — DISCARD.** More trips = more travel overhead.

### Exp 4: stuck_threshold=10
avg 1146.65 → **-3.6% — DISCARD.** Too-frequent replanning wastes steps.

### Exp 5: stuck_threshold=20
avg 1191.52 → **+0.2% — within noise.**

### Exp 6: heart accumulation cap=8 (post-early)
avg 1153.77 → **-3.0% — DISCARD.** Higher cap delays hub departure.

### Exp 7: Fast first deposit (miners rush at 28 load before first heart crafted)
Implemented early_rush mechanic for miners. Found critical bug: restructuring elif chain consumed timeout check, causing miners to get stuck mining 0 resources for 2800 steps. After fix, still -1.1%. **DISCARD.** Reverted.

### Exp 8: No sentinel (all aligners convert)
6-seed comparison: modified avg 1172.77 vs baseline 1173.96 → **-0.1% — essentially neutral.** Keeping sentinel for online safety (needs someone to recapture scrambled junctions).

### Exp 9: Mining mode threshold=40 (conservative)
Identical to baseline (neutral). Mining mode threshold doesn't matter in offline eval.

## Summary

- **Mining mode implemented and kept**: Dynamic aligner→miner conversion after junction saturation. Neutral in offline eval, potentially beneficial in online (more hearts for recapture). Sentinel aligner exemption preserved for online resilience.
- **Offline ceiling confirmed**: 9 experiments this session + 55+ prior = 64+ experiments total. The 3A/5M baseline at ~1189 avg is essentially optimal for this map. The +3.9% ceiling from prior sessions remains the best improvement.
- **Key bottleneck**: Steps 54-162 where aligners are heartless waiting for miner deposits. This is a timing constraint (first miner deposit at ~step 100), not a design flaw.
- **All parameter variations regress**: return_load, stuck_threshold, heart_cap changes all hurt. Default values are well-calibrated.

2026-05-21T07:25Z: Committing mining mode code + experiment logs
