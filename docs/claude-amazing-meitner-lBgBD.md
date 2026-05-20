# autoresearch: issue #75 — scripted policy improvements for long episodes

Branch: `claude/amazing-meitner-lBgBD`
Target issue: [#75](https://github.com/SolbiatiAlessandro/cogames/issues/75) — priority:2

## Context

Issue #78 (priority:1, auth token expired) still blocks ALL online submissions.
Issue #77 (RAxer bug fixes) resolved — merged to main with +4.4% offline.
RL training (#75) has plateaued at 1.394 avg @10K steps, while scripted achieves 4371 @10K (on arena).
No GPU available — focusing on scripted policy improvements.

## Critical fix: run_experiment.py was using wrong map

The `run_experiment.py` script used a dict to look up missions, which kept the LAST
"basic" mission (arena 50×50) instead of the first (Machina1 88×88 competition map).
All previous offline experiments were on the wrong map! Fixed by using list-based lookup.

Previous arena results (50×50, ~1K steps max_steps): 4371 avg @10K — near theoretical ceiling.
Machina1 results (88×88, 10K max_steps): ~30 avg @10K — huge room for improvement.

## Key finding: gear contamination from HP death

On the Machina1 map, aligners routinely die from HP drain outside friendly territory.
Territory control radius: hub=20 cells, junction=10 cells. HP drains -1/tick everywhere,
territory heals +100/tick. Agents start with 50 HP, max 100.

When HP reaches 0, agents lose ALL gear and respawn. Each re-gearing costs ~50-100 steps.
Baseline: 13 gear loss events per 10K episode (tracked via `aligner.gained/lost` stats).

## Experiment: HP retreat for aligners

Re-enabled `_read_hp()` which was intentionally returning None (to avoid oscillation).
Added hysteresis-based retreat: trigger at 50% HP, resume at 80% HP. Territory heals
instantly (+100/tick), so recovery is fast.

**Machina1 10K results (avg of seeds 42, 43, 44):**

| Config | Reward | aligner.gained/lost | Delta |
|--------|--------|---------------------|-------|
| Baseline (no HP retreat) | 29.95 | 13.3 | — |
| HP retreat 50% | 31.18 | 14.3 | +4.1% |

Per-seed breakdown:

| Seed | Baseline | HP retreat | Delta |
|------|----------|------------|-------|
| 42 | 36.54 | 40.04 | +9.6% |
| 43 | 20.41 | 20.61 | +1.0% |
| 44 | 32.90 | 32.90 | +0.0% |

## Changes made

1. `scripts/run_experiment.py`: Fixed mission lookup to use first "basic" mission (Machina1)
2. `src/cogames/policy/aligner_agent.py`: `_read_hp()` now returns actual HP value
3. `src/cogames/policy/machina_llm_roles_policy.py`:
   - `_check_hp()`: Retreat at 50% HP, resume at 80% (hysteresis prevents oscillation)
   - Retreat navigation uses `avoid_hazards=True` and proper BFS for junction targets

## Next steps

- The +4.1% from HP retreat is modest. Main bottleneck is likely JUNCTION DISCOVERY and ALIGNMENT SPEED, not deaths.
- Investigate why some seeds (43) perform much worse — may be map layout dependent
- Try increasing aligner fraction (4A4M instead of 3A5M) on Machina1
- Consider adaptive exploration that targets junction-rich areas
