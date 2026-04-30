# Experiment Log: claude/amazing-meitner-7T3EK

## Issue: #55 - Submit NiskB efficiency fixes + validate online (target: score > 37.0)

**2026-04-30 10:30**: autoresearch starting. My plan is to:
1. Run 5-seed offline validation at 3k steps to confirm the +3.6% improvement from NiskB's efficiency fixes (approach side diversification + fast mine depletion detection) that are now merged to main
2. Submit the policy as `lessandro-ohm-mani-padme-hum` to beta-cvc season
3. Monitor 20+ matches to see if online score exceeds 37.0

The key insight from prior research is that behavioral changes (v53-v58) and A* navigation all regressed online despite offline gains. NiskB's changes are structural efficiency improvements (not behavioral changes), so they should be safer to port online.

**2026-04-30 10:30**: starting to run baseline (5 seeds: 42, 123, 456, 789, 1024)

**2026-04-30 10:33**: baseline results (pre-NiskB, commit cbbc1e9, 3k steps):
- Seed 42: 826.43 (hearts=49, junctions=45)
- Seed 123: 799.25 (hearts=50, junctions=46)
- Seed 456: 808.62
- Seed 789: 866.70
- Seed 1024: 889.70 (hearts=51, junctions=47)
- **Average: 838.14**

Note: absolute values differ from NiskB's baseline (1079.65 avg) due to mettagrid version difference (PyPI 0.15.0 vs git-pinned build). Relative comparisons are valid since both baseline and experiment use same setup.

**2026-04-30 10:35**: NiskB experiment results (post-merge, commit 258e052, 3k steps):
- Seed 42: 1121.22 (hearts=64) — **+35.7%**
- Seed 123: 1073.88 (hearts=61) — **+34.4%**
- Seed 456: 1090.76 (hearts=63) — **+34.9%**
- Seed 789: 1103.41 (hearts=72) — **+27.3%**
- Seed 1024: 1004.18 (hearts=71) — **+12.9%**
- **Average: 1078.69 — +28.7% improvement**

Massive improvement across all seeds. The NiskB changes include:
1. Approach side diversification (agent_id % 4)
2. Fast mine depletion detection (threshold 20→8)
3. Verified hubs/extractors (prevent phantom station contamination)
4. Safe wander (avoid hazard stations)
5. Dynamic return_load (adapt to number of active miners)
6. Junction tracking (friendly/enemy/neutral)
7. Heart accumulation near hub
8. Agent position broadcasting

The +28.7% is much larger than NiskB's original +3.6% because our baseline is pre-all the intermediate fixes (sessions 17-22), whereas NiskB measured delta against v52 which already had many improvements.

**Decision**: Confirmed improvement. Proceeding with online submission as `lessandro-ohm-mani-padme-hum`.

**2026-04-30 10:36**: Submitted `lessandro-ohm-mani-padme-hum:v1` to beta-cvc qualifying pool.
- Policy version ID: 986b6089-50ab-4a96-9267-a5e215dac17c
- Bundle: 80 KB (src/cogames/policy/*.py)
- Config: scripted_miners=True, scripted_aligners=True
- Season: beta-cvc (compat 0.25)
- Pool: qualifying
- Expected: score > 37.0 (current v52 baseline: 36.18 at #25)

Now monitoring qualifying matches...

**2026-04-30 10:50**: 10k step offline analysis (seed 42, post-NiskB):
- Total reward: 4144.70 (3.70x the 3k result of 1121.22 for 3.33x steps — slightly super-linear)
- Hearts gained: 64 at 10k = same as at 3k → all hearts captured by ~3k steps
- Junctions aligned: 53 at 10k = same as at 3k → all alignment done by ~3k steps
- HP: gained=80400, lost=80000, remaining=800/800 → **0 deaths in self-play**
- max_steps_without_motion: 87 (good, no major stuck)

Key insight: No deaths in offline self-play. Deaths are an online-only problem (combat damage from enemy clips). This confirms issue #56's hypothesis.

**2026-04-30 10:55**: Online qualifying completed — policy passed qualifying (2 self-play matches). 20 main pool matches scheduled (12 scheduled, 8 running).

**2026-04-30 11:00**: starting new experiment loop. While waiting for online results, I want to try improving late-game agent survival. My hypothesis is that agents who stay near aligned junctions after resource depletion will hold junctions longer and avoid wandering into enemy territory where they take combat damage.
