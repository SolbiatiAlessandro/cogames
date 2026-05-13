# Experiment Log: claude/amazing-meitner-JNxDg

## Issue: #71 — Junction control efficiency — 74% vs Softy's 84%

2026-05-13 16:00: autoresearch starting, my plan is to:
1. Run baseline on current main HEAD (14c7ac6)
2. Analyze junction control bottlenecks from baseline stats
3. Focus on improvements identified by previous researchers:
   - End-game heart hoarding (6-14 unused hearts at episode end)
   - Adaptive aligner count based on episode phase
   - Miner junction deposit (from 2ND7G branch, +4.7%)
   - Aligner spread bonus (from Vt4ZB branch, +7.3%)
   - 5A+3M configuration (from toEqP branch, +3.2%)
   - HUB_ALIGN_DISTANCE=30 (from toEqP, +24% junction held)
4. Previous researchers found +29% cumulative improvement (3.469 vs 2.690 baseline)
5. Director noted toEqP changes were NOT merged to main — need integration

Key context from director session 35:
- Agent lifespan consistency is the root cause of the gap (our 2147-7550 vs Softy's 5500±60)
- Junction targeting & spread: partially addressed (spread bonus merged)
- Heart acquisition efficiency: partially addressed (heart bug fix merged)
- Miner resource delivery: partially addressed (junction deposit merged)

2026-05-13 16:00: starting to run baseline

## Baseline results

5-seed avg (seeds 42/123/7/99/555, 8 agents, 3000 steps): **131.76 avg_per_agent**

## Experiment 1: Heart progress bug fix (commit a86628c)

**Hypothesis:** The heart progress tracking was using current state instead of previous state, causing made_progress to fire incorrectly.

**Change:** Save `prev_has_heart` and `prev_friendly_count` before updating state in `_update_progress`. Compare against previous values.

**Result:** +1.3% (133.50 avg) — minor improvement from fixing progress tracking.

**Status:** KEEP

## Experiment 2: Heart accumulation tuning (commit 33092a1)

**Change:** Increased heart accumulation stale threshold from 3 to 5 steps near hub (`heart_count < 3 and no_progress < 5`).

**Result:** +2.6% cumulative (135.21 avg).

**Status:** KEEP

## Experiment 3: return_load=35 (commit d7ce9cb)

**Hypothesis:** Earlier sweep showed return_load=35 optimal.

**Change:** Default return_load from 40 to 35.

**Finding:** return_load has NO EFFECT — miners always complete at load=40 regardless of threshold. Resources come in batches that jump past 35. return_load=32, 35, 40 all produce IDENTICAL results.

**Status:** REVERTED (commit d472167)

## Experiment 4: Nearest-junction targeting (commit 08349a8) ★ KEY WIN

**Hypothesis:** Hub-distance bias in `_cascade_priority_target` (weight=0.2) adds unnecessary travel. Agents should simply go to the nearest junction.

**Change:** Replaced cascade scoring with pure nearest-junction selection.

**Sweep results:**
| hub_dist weight | 5-seed avg | vs baseline |
|----------------|-----------|-------------|
| 0.3            | 139.9     | +6.2%       |
| 0.2 (old)      | 138.7     | +5.3%       |
| 0.1            | 139.9     | +6.2%       |
| 0.001          | 139.6     | +5.9%       |
| **0.0 (new)**  | **142.0** | **+7.8%**   |
| -0.001         | 138.0     | +4.7%       |

**Result:** 142.02 avg (+7.8% over baseline). Pure nearest-junction is optimal.

**Status:** KEEP

## Experiments that FAILED (all reverted)

| Experiment | Change | 5-seed avg | vs best | Status |
|-----------|--------|-----------|---------|--------|
| HUB_ALIGN_DISTANCE=30 | Widen hub alignment range | 135.60 | -4.5% | REVERT |
| Heart accumulation finish=4 | Align finish with plan (4 hearts) | 138.45 | -2.5% | REVERT |
| Heart queue max(2) | Restrict hub access | 133.55 | -6.0% | REVERT |
| Heart queue max(4) | More hub access | 133.60 | -5.9% | REVERT |
| No heart queue | Remove limit entirely | 133.60 | -5.9% | REVERT |
| stuck_threshold=15 | Faster stuck detection | 135.66 | -4.5% | REVERT |
| Explore cap=60 | Longer explore | 138.48 | -2.5% | REVERT |
| Explore cap=30 | Shorter explore | 134.76 | -5.1% | REVERT |
| Nav shake threshold=3 | Faster deadlock break | 139.11 | -2.1% | REVERT |
| JUNCTION_ALIGN_DISTANCE=15 | Match game engine (15) | 136.98 | -3.5% | REVERT |
| JUNCTION_ALIGN_DISTANCE=20 | Compromise value | 138.52 | -2.5% | REVERT |
| JUNCTION_ALIGN_DISTANCE=35 | More permissive | 138.83 | -2.2% | REVERT |
| No junction coordination | Remove aligner target blacklist | 138.06 | -2.8% | REVERT |
| 5A+3M composition | More aligners | 132.49 | -6.7% | REVERT |
| 3A+5M composition | More miners | 130.12 | -8.4% | REVERT |
| Miner junction deposit | Deposit at friendly junctions | 133.15 | -6.2% | REVERT |
| Enemy junction priority | -10 score for enemy junctions | 142.02 | 0% (no enemy junctions in self-play) | REVERT |

## Key learnings

1. **Nearest-junction targeting is the biggest win** — removing hub-distance bias reduces travel time and lets agents capture junctions faster.
2. **Most parameters are already well-tuned** — stuck_threshold=20, heart queue=max(3), 4A+4M, JUNCTION_ALIGN_DISTANCE=25 are all local optima.
3. **return_load has no effect** in the 32-40 range because miners batch-mine to 40 regardless.
4. **Junction deposit doesn't work** — either the game mechanic doesn't support it or it causes miners to get stuck at junctions.
5. **Self-play doesn't capture online dynamics** — enemy junctions, HP drain, transit congestion are absent in self-play.
6. **Policy's JUNCTION_ALIGN_DISTANCE=25 > game's 15** is intentionally permissive and helps — the policy doesn't perfectly track all net:cogs entities, so the extra range compensates.

## Next directions for future researchers

- The remaining gap (74% vs 84%) likely requires structural changes:
  - Agent lifespan consistency (our 2147-7550 vs Softy's 5500±60)
  - Online-specific tuning (HP retreat, transit handling)
  - Potentially different architecture (not scripted planner)
- Upload current changes to online tournament for validation
- Consider whether the offline metric (avg_per_agent at 3k steps) correlates with online performance
